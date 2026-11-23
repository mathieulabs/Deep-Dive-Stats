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
from .trace import page_log, trace, traces_on
from .update_restart import ask_restart, is_stale_import


_PARSE_FROM = 20000


def _js(payload):
    """payload as a value in the page's script: compact single-pass JSON, wrapped in JSON.parse
    when large (~2x faster for Chromium to parse than an inline object literal)."""
    try:
        s = json.dumps(payload, separators=(",", ":"), allow_nan=False)
        strict = True
    except ValueError:
        # NaN / Infinity (a float of a chart's data) read in a script, not by JSON.parse
        s = json.dumps(payload, separators=(",", ":"))
        strict = False
    if len(s) < _PARSE_FROM or not strict:
        return s
    return "JSON.parse(" + json.dumps(s) + ")"


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

    def _eval_js(self, request_id, ok, js_val):
        if self._closed:
            return 0.0
        import time

        t0 = time.perf_counter()
        try:
            self._web.eval(f"DD.__resolve({request_id}, {'true' if ok else 'false'}, {js_val})")
        except Exception as e:  # the page is gone
            log_warn(f"bridge resolve: {e!r}", tag="WEB")
        return 1000 * (time.perf_counter() - t0)

    def _resolve(self, request_id, ok, payload):
        if self._closed:
            return (0.0, 0.0, 0)
        import time

        t0 = time.perf_counter()
        js_val = _js(payload)
        ser_ms = 1000 * (time.perf_counter() - t0)
        eval_ms = self._eval_js(request_id, ok, js_val)
        return (ser_ms, eval_ms, len(js_val))

    def push(self, event, payload=None):
        self._web.eval(f"DD.__push({json.dumps(event)}, {_js(payload)})")

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
            # dev trace: when the thread started it and how long it ran, apart from the wait before it started
            # (queued behind other background work) and the wait after (on_done, run on the UI thread)
            span = {}

            def _run(handler=handler, args=args, span=span):
                span["start"] = time.perf_counter()
                try:
                    res = ui_first(handler, **args)
                    t_s0 = time.perf_counter()
                    js_val = _js(res)
                    span["ser_ms"] = 1000 * (time.perf_counter() - t_s0)
                    span["bytes"] = len(js_val)
                    return js_val
                finally:
                    span["end"] = time.perf_counter()

            def _done(fut, request_id=request_id, cmd=cmd, span=span):
                t_done = time.perf_counter()
                try:
                    js_val = fut.result()
                    ser_ms = span.get("ser_ms", 0.0)
                    nbytes = span.get("bytes", len(js_val))
                    eval_ms = self._eval_js(request_id, True, js_val)
                except Exception as e:
                    log_error(f"web bridge {cmd!r}: {e!r}")
                    if is_stale_import(e):
                        ask_restart(e)
                    ser_ms, eval_ms, nbytes = self._resolve(request_id, False, repr(e))
                ms = 1000 * (time.perf_counter() - t0)
                if traces_on() and (ms >= 15 or cmd in ("data", "zoom_stats", "adaptive", "stats", "table", "first_data")):
                    st, en = span.get("start", t0), span.get("end", t0)
                    run_only = max(0.0, 1000 * (en - st) - ser_ms)
                    trace(
                        f"PERFTRACE bridge {cmd} bg total={ms:.0f}ms wait={1000 * (st - t0):.0f}ms"
                        f" run={run_only:.0f}ms ser_bg={ser_ms:.1f}ms ui={1000 * (t_done - en):.0f}ms"
                        f" eval={eval_ms:.1f}ms kb={nbytes / 1024:.1f}"
                    )

            # dev trace (RESIZETRACE): the background commands running, by name and start time
            self._inflight[request_id] = (cmd, t0)
            _inner = _done

            def _done(fut, _inner=_inner, request_id=request_id):
                self._inflight.pop(request_id, None)
                _inner(fut)

            from .ui_share import ui_first

            mw.taskman.run_in_background(_run, on_done=_done)
            return None
        try:
            handler = self._handlers[request["cmd"]]
            payload = handler(**(request.get("args") or {}))
            ok = True
            run_ms = 1000 * (time.perf_counter() - t0)
        except Exception as e:  # the page gets the error, the log gets the trace
            log_error(f"web bridge {request.get('cmd')!r}: {e!r}")
            if is_stale_import(e):
                ask_restart(e)
            payload, ok = repr(e), False
            run_ms = 1000 * (time.perf_counter() - t0)
        ser_ms, eval_ms, nbytes = self._resolve(request_id, ok, payload)
        total_ms = 1000 * (time.perf_counter() - t0)
        if traces_on() and total_ms >= 10:
            trace(
                f"PERFTRACE bridge {cmd} ui total={total_ms:.0f}ms run={run_ms:.1f}ms"
                f" ser={ser_ms:.1f}ms eval={eval_ms:.1f}ms kb={nbytes / 1024:.1f}"
            )
        return None
