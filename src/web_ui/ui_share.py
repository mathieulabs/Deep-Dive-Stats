# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The UI thread's share of Python's lock while the add-on computes in the background.

A background computation in pure Python (FSRS fatigue, siblings, leech odds...) keeps Python's lock and hands
it over only every "switch interval" (5 ms). Anki's UI thread runs Python many times a frame (event filters,
timers, the page's messages), and on Windows each of its waits for the lock lasted ~15 ms (the clock's step): a
frame of the open window waited 120 to 180 ms, the page's animations and scroll stuttered with nothing to do.
With 0.5 ms the UI thread gets the lock back at once (a frame of 25 callbacks: 380 ms -> 1 ms in a test), the
computation ~5% slower. Only while a computation of the add-on runs: the interval is put back after the last."""

import sys
import threading

_INTERVAL = 0.0005
_lock = threading.Lock()
_state = {"n": 0, "saved": None}


def _enter():
    with _lock:
        if _state["n"] == 0:
            _state["saved"] = sys.getswitchinterval()
            if _state["saved"] > _INTERVAL:
                sys.setswitchinterval(_INTERVAL)
        _state["n"] += 1


def _leave():
    with _lock:
        _state["n"] = max(0, _state["n"] - 1)
        if _state["n"] == 0 and _state["saved"] is not None:
            # put back only our own value: someone else's change meanwhile is left as it is
            if abs(sys.getswitchinterval() - _INTERVAL) < 1e-9:
                sys.setswitchinterval(_state["saved"])
            _state["saved"] = None


def ui_first(fn, *a, **kw):
    """fn(*a, **kw) in a background thread, the UI thread getting Python's lock back quickly meanwhile."""
    _enter()
    try:
        return fn(*a, **kw)
    finally:
        _leave()
