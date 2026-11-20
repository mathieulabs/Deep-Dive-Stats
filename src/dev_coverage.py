# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Development recorder of the add-on's code that actually runs (source checkout only).

Every function of the add-on that runs is noted once (sys.monitoring, the event turned off for that function after
its first call, so it costs nothing after). The list is merged into user_files/dev_coverage.json every minute and
when the profile closes: over days of use it tells the code that still serves from the code nothing calls."""

import json
import os
import sys
import threading

_TOOL = 4  # a free sys.monitoring tool id (0-5); 0, 1, 2, 5 are taken by debuggers, coverage and profilers
_s = {"on": False, "seen": set(), "dirty": False, "lock": threading.Lock()}
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_ROOT, "src") + os.sep


def _path():
    return os.path.join(_ROOT, "user_files", "dev_coverage.json")


def _on_start(code, _offset):
    f = code.co_filename
    if f.startswith(_SRC):
        with _s["lock"]:
            _s["seen"].add((f[len(_SRC):].replace(os.sep, "/"), code.co_firstlineno, code.co_qualname))
            _s["dirty"] = True
    return sys.monitoring.DISABLE


def save():
    """Merge what ran since the last save into the file."""
    if not _s["on"] or not _s["dirty"]:
        return
    with _s["lock"]:
        seen = set(_s["seen"])
        _s["dirty"] = False
    try:
        p = _path()
        old = []
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                old = json.load(fh).get("ran", [])
        merged = sorted({tuple(x) for x in old} | seen)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"ran": merged}, fh)
        os.replace(tmp, p)
    except Exception:
        pass


def start():
    """Turned on in a source checkout (dev_tools/ present) whose Python has sys.monitoring (3.12+)."""
    if _s["on"] or not hasattr(sys, "monitoring"):
        return
    from .config import is_dev_build

    if not is_dev_build():
        return
    m = sys.monitoring
    try:
        m.use_tool_id(_TOOL, "deep_dive_coverage")
    except ValueError:
        return
    m.register_callback(_TOOL, m.events.PY_START, _on_start)
    m.set_events(_TOOL, m.events.PY_START)
    _s["on"] = True
    try:
        from aqt import gui_hooks
        from aqt.qt import QTimer

        t = QTimer()
        t.timeout.connect(save)
        t.start(60_000)
        _s["timer"] = t
        gui_hooks.profile_will_close.append(save)
    except Exception:
        pass
