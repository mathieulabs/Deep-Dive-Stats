# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Development probe of Anki's first seconds (source checkout only, tag STARTUP in debug.log).

A timer on the UI thread ticks every 20 ms; a side thread watches it. When the UI thread stops ticking (Anki
frozen) the side thread samples what the UI thread is running every 20 ms. Once it ticks again, one line per
freeze: how long, after which step (mark()), and the code it was in most of the time (the add-on's frames first)."""

import os
import sys
import threading
import time
import traceback
from collections import Counter

_WINDOW_S = 45.0      # watched for the first 45 s after the add-on loads
_TICK_MS = 20
_STALL_MS = 120       # a freeze: the UI thread did not tick for this long
_HITCH_MS = 60        # a hitch: shorter, logged on one line (a dropped frame or a few, not a freeze)

_s = {"t0": None, "beat": 0.0, "marks": [], "stalls": [], "lock": threading.Lock(), "timer": None, "on": False}


def _dev():
    try:
        from ..config import is_dev_build

        return is_dev_build()
    except Exception:
        return False


def _log(msg):
    try:
        from ..details.logic.logger import log_warn

        log_warn(msg, tag="STARTUP")
    except Exception:
        pass


def _ms():
    return (time.perf_counter() - _s["t0"]) * 1000.0 if _s["t0"] else 0.0


def mark(label):
    """A step of the start (UI thread): logged with its time, and named in the freezes that follow it."""
    if not _s["on"]:
        return
    t = _ms()
    _s["marks"].append((t, label))
    _log(f"t={t:.0f}ms {label}")


def timed(_label, _fn, /, *a, **kw):
    """_fn(*a, **kw), logged when it took 15 ms or more during the watched window. Its own two arguments are
    positional only: a handler's keyword named "label" (a chart's bar clicked, for the browser) clashed with them."""
    if not _s["on"]:
        return _fn(*a, **kw)
    t = time.perf_counter()
    try:
        return _fn(*a, **kw)
    finally:
        dt = (time.perf_counter() - t) * 1000.0
        if dt >= 15:
            _log(f"t={_ms():.0f}ms {_label} took {dt:.0f}ms (UI thread)")


_ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _short(frames):
    """The stack as a few 'file:function:line' steps: the add-on's own, plus the deepest frame (where it was)."""
    own = [f for f in frames if f.filename.startswith(_ADDON)]
    pick = own[-4:] if own else frames[-3:]
    if frames and frames[-1] not in pick:
        pick = pick + [frames[-1]]
    out = []
    for f in pick:
        name = f.filename[len(_ADDON) + 1:] if f.filename.startswith(_ADDON) else os.path.basename(f.filename)
        out.append(f"{name}:{f.name}:{f.lineno}")
    return " > ".join(out)


def _watch(main_id):
    stall = None
    end = time.perf_counter() + _WINDOW_S + 5
    while time.perf_counter() < end and _s["on"]:
        time.sleep(_TICK_MS / 1000.0)
        late = (time.perf_counter() - _s["beat"]) * 1000.0
        if late >= _HITCH_MS:
            if stall is None:
                stall = {"start": _ms() - late, "stacks": Counter(), "n": 0, "others": Counter()}
            frames = sys._current_frames()
            frame = frames.get(main_id)
            if frame is not None:
                try:
                    st = traceback.extract_stack(frame)
                    stall["stacks"][_short(st)] += 1
                    stall["n"] += 1
                    # the UI thread in Qt's own code (its event loop the deepest Python frame): stalled in Qt, or
                    # waiting for Python's lock another thread holds. What the other threads ran tells which
                    if st and st[-1].name == "_run":
                        me = threading.get_ident()
                        names = {t.ident: t.name for t in threading.enumerate()}
                        for tid, fr in frames.items():
                            if tid in (main_id, me):
                                continue
                            ost = traceback.extract_stack(fr)
                            if ost and ost[-1].name in ("wait", "_worker", "get", "select", "accept", "recv", "readline"):
                                continue  # an idle thread (a pool waiting for work, a socket)
                            stall["others"][f"[{names.get(tid, tid)}] {_short(ost)}"] += 1
                except Exception:
                    pass
        elif stall is not None:
            stall["dur"] = _ms() - stall["start"]
            with _s["lock"]:
                _s["stalls"].append(stall)
            stall = None


def _tick():
    _s["beat"] = time.perf_counter()
    with _s["lock"]:
        stalls, _s["stalls"] = _s["stalls"], []
    for st in stalls:
        before = [m for m in _s["marks"] if m[0] <= st["start"] + 1]
        after = before[-1][1] if before else "the add-on loading"
        if st["dur"] < _STALL_MS:
            # a hitch: the UI thread's deepest step and the busiest other thread, on one line
            top = st["stacks"].most_common(1)
            oth = st.get("others", Counter()).most_common(1)
            _log(f"HITCH {st['dur']:.0f}ms at t={st['start']:.0f}ms: UI {top[0][0].split(' > ')[-1] if top else '?'}"
                 + (f" | other: {oth[0][0]}" if oth else ""))
            continue
        _log(f"FREEZE {st['dur']:.0f}ms at t={st['start']:.0f}ms (after: {after}), {st['n']} samples")
        for stack, n in st["stacks"].most_common(4):
            _log(f"   {n * 100 // max(1, st['n'])}% {stack}")
        for stack, n in st.get("others", Counter()).most_common(3):
            _log(f"   other thread, {n * 100 // max(1, st['n'])}%: {stack}")
    if _ms() > _WINDOW_S * 1000 and _s["timer"] is not None:
        _s["timer"].stop()
        _s["on"] = False
        _log(f"probe over ({_WINDOW_S:.0f} s)")


def _log_bytecode():
    """Whether Python keeps the add-on's compiled files (.pyc): without them every start compiles all the code it
    imports again (seen on a phone)."""
    try:
        import importlib.util

        pyc = importlib.util.cache_from_source(__file__)
        _log(f"python {sys.version.split()[0]}: dont_write_bytecode={sys.dont_write_bytecode} "
             f"pycache_prefix={sys.pycache_prefix!r} this module's .pyc {'found' if os.path.exists(pyc) else 'missing'}: {pyc}")
    except Exception as e:
        _log(f"bytecode check failed: {e!r}")


def start():
    """At the add-on's load (UI thread). Nothing outside a source checkout."""
    if _s["on"] or not _dev():
        return
    try:
        from aqt.qt import QTimer

        _s["t0"] = _s["beat"] = time.perf_counter()
        _s["on"] = True
        tm = QTimer()
        tm.setInterval(_TICK_MS)
        tm.timeout.connect(_tick)
        tm.start()
        _s["timer"] = tm
        threading.Thread(target=_watch, args=(threading.get_ident(),), daemon=True, name="dd-startup-probe").start()
        from aqt import gui_hooks

        for name in ("main_window_did_init", "profile_did_open", "collection_did_load", "deck_browser_did_render",
                     "overview_did_refresh", "sync_will_start", "sync_did_finish"):
            hook = getattr(gui_hooks, name, None)
            if hook is not None:
                hook.append(lambda *a, _n=name: mark("hook " + _n))
        _log("probe on: freezes of the UI thread over 120 ms are logged with what ran")
        _log_bytecode()
    except Exception as e:
        _s["on"] = False
        _log(f"probe failed: {e!r}")
