# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Switch the Activity chart to one dot per review when zoomed on a few hours."""
from datetime import datetime

from aqt.qt import QTimer

from ....logic.history_provider import HistoryProvider
from ....widgets.chart_utils.zoom_camera import switch_stack
from ....logic.history_provider.ops.review_events import fetch_review_events
from ....logic.logger import log_debug, log_swallowed
from ....widgets.charts.activity.review_dots import DOTS_MAX_SPAN_MS

BIN_MS = 600000


def refresh_review_dots(manager, immediate=False):
    """Debounced (unless immediate). Does nothing unless the Activity chart is in the
    10-minute view or already showing dots."""
    dots = getattr(manager, "review_dots_chart", None)
    stack = getattr(manager, "activity_stack", None)
    if dots is None or stack is None:
        return
    try:
        showing = stack.currentIndex() == 2
    except RuntimeError:
        return
    if not showing and not getattr(manager, "_adaptive_zoom_active", False):
        return
    if immediate:
        timer = getattr(manager, "_review_dots_timer", None)
        if timer is not None:
            timer.stop()
        _apply(manager)
        return
    timer = getattr(manager, "_review_dots_timer", None)
    if timer is None:
        timer = QTimer(manager.dialog)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: _apply(manager))
        manager._review_dots_timer = timer
    timer.start(120)


def _zoomed_chart(manager):
    candidates = [getattr(manager, "stacked_chart", None), getattr(manager, "activity_chart", None)]
    if not manager.last_activity_breakdown:
        candidates.reverse()
    return next((c for c in candidates if c is not None and getattr(c, "_is_zoomed", False)), None)


def _parse(date_str):
    return int(datetime.strptime(date_str, "%Y-%m-%d %H:%M").timestamp() * 1000)


def _show_bars(manager, stack):
    if stack.currentIndex() == 2 or getattr(stack, "_pending_switch", None) is not None:
        switch_stack(stack, 1 if (manager.last_activity_breakdown and manager.stacked_chart) else 0, "details")


def _zoom_out(manager, frac):
    """Ctrl+wheel out of the full dots window: widen the zoom by a step right away (the
    dots glide to the wider window, or the bars take over once it is over the dots limit)
    instead of waiting for the debounced refresh. False: cannot widen, let the chart do it."""
    from bisect import bisect_left, bisect_right

    dots = getattr(manager, "review_dots_chart", None)
    chart = _zoomed_chart(manager)
    rows = getattr(manager, "_hi_res_history", None)
    if dots is None or chart is None or not rows or not getattr(manager, "_adaptive_zoom_active", False):
        return False
    if not hasattr(chart, "_pre_adaptive_data"):
        return False
    cache = getattr(manager, "_hi_res_times", None)
    if cache is None or cache[0] is not rows or cache[1] != len(rows):
        cache = (rows, len(rows), [_parse(r["date"]) for r in rows])
        manager._hi_res_times = cache
    times = cache[2]
    cs, ce = chart.get_zoom_range()
    cs, ce = max(0, int(cs)), min(len(rows), int(ce))
    t0, t1 = dots._t0, dots._t1
    new_span = (t1 - t0) * 1.25
    n0 = t0 + frac * (t1 - t0) - frac * new_span
    n1 = n0 + new_span
    s = max(0, bisect_right(times, n0) - 1)
    e = min(len(rows), bisect_left(times, n1 - BIN_MS) + 1)
    s, e = min(s, cs), max(e, ce)
    if s == cs and e == ce:
        s, e = max(0, cs - 1), min(len(rows), ce + 1)
    if s >= cs and e <= ce:
        return False
    chart.set_zoom_range(s, e)
    refresh_review_dots(manager, immediate=True)
    return True


def _apply(manager):
    try:
        dots = getattr(manager, "review_dots_chart", None)
        stack = getattr(manager, "activity_stack", None)
        if dots is None or stack is None:
            return
        chart = _zoomed_chart(manager)
        rows = getattr(manager, "_hi_res_history", None)
        if chart is None:
            _show_bars(manager, stack)
            return
        if getattr(manager, "_adaptive_zoom_active", False) and rows and hasattr(chart, "_pre_adaptive_data"):
            start, end = chart.get_zoom_range()
            end = min(int(end), len(rows))
            start = max(0, int(start))
            if end - start < 1:
                _show_bars(manager, stack)
                return
            t0 = _parse(rows[start]["date"])
            t1 = _parse(rows[end - 1]["date"]) + BIN_MS
            if t1 - t0 > DOTS_MAX_SPAN_MS:
                _show_bars(manager, stack)
                return
        else:
            _show_bars(manager, stack)
            return
        row_data = manager.last_row_data or {}
        events = fetch_review_events(
            HistoryProvider,
            manager.addon_config,
            row_data.get("did"),
            row_data.get("is_deleted", False),
            t0,
            t1,
        )
        if events is None:
            _show_bars(manager, stack)
            return
        from ....logic.data.transforms.activity_series import normalize_hidden_types

        hidden = normalize_hidden_types(manager._get_dd_widget_setting("activity", "hidden_review_types", None))
        if hidden:
            kind_keys = ("learn", "young", "mature", "relearn", "cram")
            events = [e for e in events if kind_keys[e[3]] not in hidden]
        time_mode = bool(manager._get_dd_widget_setting("activity", "show_time_axis", False))
        dots.set_mode("time" if time_mode else "reviews", manager.last_activity_breakdown)
        dots.set_events(events, t0, t1)
        dots.wheel_target = chart
        dots.zoom_out_handler = lambda frac, m=manager: _zoom_out(m, frac)
        switch_stack(stack, 2, "details")
        log_debug(f"[DOTS] {len(events)} reviews shown", tag="DEEPDIVE")
    except Exception:
        log_swallowed()
