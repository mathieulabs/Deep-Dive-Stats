# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The reads of the charts that fetch their own data in the background (Introduced, Answer
Time, Rating by Interval, Week by Hour, Card Counts over Time).

They go one at a time, and only once the window has been quiet for a moment after the last
request: on a deck change Deep Dive first animates the charts it already has the data of,
then these update one after the other. Started all at once, they competed with that
animation (each one a query of the whole review history, and the collection answers one
query at a time), so the whole window stuttered."""

from aqt import mw
from aqt.qt import QTimer

from ....logic.logger import log_swallowed

DELAY_MS = 350  # quiet time after the last request before the reads start

_queue = []  # [(key, work, done)]
_state = {"running": False, "timer": None}


def _timer():
    t = _state["timer"]
    if t is None:
        t = QTimer()
        t.setSingleShot(True)
        t.setInterval(DELAY_MS)
        t.timeout.connect(_next)
        _state["timer"] = t
    return t


def run(key, work, done, wait=True):
    """work() in the background, then done(future) on the main thread. A request with the
    same key as one still waiting replaces it (only the last deck or period is read).
    wait=False: no quiet time first (a refresh is waiting for this data to animate it with
    the other charts, see ui.deep_dive.extra_charts)."""
    _queue[:] = [q for q in _queue if q[0] != key]
    if wait:
        _queue.append((key, work, done))
    else:
        # Ahead of the reads that only wait for a quiet moment.
        _queue.insert(0, (key, work, done))
    if not _state["running"]:
        if wait:
            _timer().start()  # (re)started: the reads wait for the window to be quiet
        else:
            _timer().stop()
            QTimer.singleShot(0, _next)


def _next():
    if _state["running"] or not _queue:
        return
    _key, work, done = _queue.pop(0)
    _state["running"] = True

    def finished(fut):
        _state["running"] = False
        try:
            done(fut)
        except Exception:
            log_swallowed()
        if _queue:
            QTimer.singleShot(0, _next)

    try:
        mw.taskman.run_in_background(work, on_done=finished)
    except Exception:
        _state["running"] = False
        log_swallowed()


def when_quiet(widget, fn, limit=None, waited_ms=0):
    """fn() once few charts are animating in widget's window (at most limit, the setting
    of how many charts may animate at once): a chart whose data comes late waits for room
    instead of adding one more animation to a screen already busy with many (at most 2 s)."""
    try:
        from ....animations.anim_driver import animations_running_in_window
        from ....animations.chart_policy import get_chart_animation_visible_threshold

        if limit is None:
            limit = max(1, int(get_chart_animation_visible_threshold()))
        busy = animations_running_in_window(widget) >= limit
    except RuntimeError:
        return  # closed meanwhile
    except Exception:
        busy = False
    if busy and waited_ms < 2000:
        QTimer.singleShot(60, lambda: when_quiet(widget, fn, limit, waited_ms + 60))
        return
    try:
        fn()
    except RuntimeError:
        pass
    except Exception:
        log_swallowed()
