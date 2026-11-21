# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Messages between a web page and Python.

Page -> Python: DD.call("name", {args}) sends "dd:{id, cmd, args}"; the handler registered under
"name" gets the args as keyword arguments, and its return value (JSON) resolves the promise.
Python -> page: push(event, payload) calls the listeners of DD.on(event, fn).
Errors in the page reach debug.log through "dd_log:" messages.
"""

import json

from ..details.logic.logger import log_error, log_warn
from .trace import page_log, trace
from .update_restart import ask_restart, is_stale_import


class Bridge:
    def __init__(self, webview, owner):
        self._web = webview
        self._handlers = {}
        self._background = set()
        self._inflight = {}
        self._closed = False
        webview.set_bridge_command(self._on_message, owner)

    def register(self, name, handler, background=False):
        """background=True: the handler runs off the UI thread (mw.taskman), so a slow read never freezes the
        window and its animations; the answer comes when it is done."""
        self._handlers[name] = handler
        if background:
            self._background.add(name)
        else:
            self._background.discard(name)

    def close(self):
        self._closed = True

    def _resolve(self, request_id, ok, payload):
        if self._closed:
            return
        try:
            self._web.eval(f"DD.__resolve({request_id}, {'true' if ok else 'false'}, {json.dumps(payload)})")
        except Exception as e:  # the page is gone
            log_warn(f"bridge resolve: {e!r}", tag="WEB")

    def push(self, event, payload=None):
        self._web.eval(f"DD.__push({json.dumps(event)}, {json.dumps(payload)})")

    def _on_message(self, message):
        if message.startswith("dd_log:"):
            page_log(message[7:])
            return None
        if not message.startswith("dd:"):
            return None
        request = json.loads(message[3:])
        request_id = request.get("id")
        import time

        t0 = time.perf_counter()
        cmd = request.get("cmd")
        if cmd in self._background:
            from aqt import mw

            handler, args = self._handlers[cmd], (request.get("args") or {})

            def _done(fut, request_id=request_id, cmd=cmd):
                try:
                    payload, ok = fut.result(), True
                except Exception as e:
                    log_error(f"web bridge {cmd!r}: {e!r}")
                    if is_stale_import(e):
                        ask_restart(e)
                    payload, ok = repr(e), False
                ms = 1000 * (time.perf_counter() - t0)
                if ms > 300:
                    trace(f"bridge {cmd!r} (background) took {ms:.0f} ms")
                self._resolve(request_id, ok, payload)

            # dev trace (RESIZETRACE): the background commands running, by name and start time
            self._inflight[request_id] = (cmd, t0)
            _inner = _done

            def _done(fut, _inner=_inner, request_id=request_id):
                self._inflight.pop(request_id, None)
                _inner(fut)

            from .ui_share import ui_first

            mw.taskman.run_in_background(lambda: ui_first(handler, **args), on_done=_done)
            return None
        try:
            handler = self._handlers[request["cmd"]]
            payload = handler(**(request.get("args") or {}))
            ok = True
            ms = 1000 * (time.perf_counter() - t0)
            if ms > 60:
                trace(f"bridge {request.get('cmd')!r} took {ms:.0f} ms")
        except Exception as e:  # the page gets the error, the log gets the trace
            log_error(f"web bridge {request.get('cmd')!r}: {e!r}")
            if is_stale_import(e):
                ask_restart(e)
            payload, ok = repr(e), False
        self._web.eval(f"DD.__resolve({request_id}, {'true' if ok else 'false'}, {json.dumps(payload)})")
        return None
