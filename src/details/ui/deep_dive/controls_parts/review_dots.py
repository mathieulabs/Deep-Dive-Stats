# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Switch the Activity chart to one dot per review when zoomed on a few hours."""
from datetime import datetime

from aqt.qt import QTimer

from ....logic.history_provider import HistoryProvider
from ....widgets.chart_utils.stack_fade import set_stack_index_animated
from ....logic.history_provider.ops.review_events import fetch_review_events
from ....logic.logger import log_debug, log_swallowed
from ....widgets.charts.activity.review_dots import DOTS_MAX_SPAN_MS

BIN_MS = 600000


def refresh_review_dots(manager):
    """Debounced. Does nothing unless the Activity chart is in the 10-minute view or already showing dots."""
    dots = getattr(manager, "review_dots_chart", None)
    stack = getattr(manager, "activity_stack", None)
    if dots is None or stack is None:
        return
    try:
        showing = stack.currentIndex() == 2
    except RuntimeError:
        return
    if not showing and not getattr(manager, "_adaptive_zoom_active", False):
        if getattr(manager, "last_sync_zoom", False) or not _zoomed_chart(manager):
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


def _window_from_daily_rows(manager, chart):
    """Zoom window in ms for the daily view (no zoom sync), only if it is 2 days or less."""
    from .... import rollover_hour
    from ....widgets.charts.common.zoom import build_adaptive_fetch_bounds, resolve_adaptive_zoom_window

    history = list(reversed(manager.last_history_data or []))
    if not history:
        return None
    start, end = chart.get_zoom_range()
    source_len = int(getattr(chart, "_full_length", 0) or len(history))
    offset = len(history) - source_len
    window = resolve_adaptive_zoom_window(
        history[max(0, int(start) + offset):max(0, min(len(history), int(end) + offset))],
        date_keys=("logical_date", "date"),
    )
    if not window:
        return None
    return build_adaptive_fetch_bounds(window["first_dt"], window["last_dt"], offset_seconds=rollover_hour() * 3600)


def _parse(date_str):
    return int(datetime.strptime(date_str, "%Y-%m-%d %H:%M").timestamp() * 1000)


def _show_bars(manager, stack):
    if stack.currentIndex() == 2:
        set_stack_index_animated(stack, 1 if (manager.last_activity_breakdown and manager.stacked_chart) else 0, "details")


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
        if getattr(manager, "_adaptive_zoom_active", False) and rows:
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
        elif not getattr(manager, "last_sync_zoom", False):
            bounds = _window_from_daily_rows(manager, chart)
            if bounds is None:
                _show_bars(manager, stack)
                return
            t0, t1 = bounds
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
        set_stack_index_animated(stack, 2, "details")
        log_debug(f"[DOTS] {len(events)} reviews shown", tag="DEEPDIVE")
    except Exception:
        log_swallowed()
