# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Zoom shared between pinned charts.

Zooming one pinned chart zooms the other connected ones to the same dates.
A chart (or all of them) can be disconnected from the right-click menu.
"""
from ...logic.logger import log_swallowed
from ..chart_utils.zoom_mixin import ZoomableMixin, remap_zoom, zoom_rows, zoom_snapshot
from ...ui.shared.zoom_span import _row_date, zoom_dates

_busy = False


def _widgets(manager):
    try:
        return [w for w in list(manager._active_widgets.values()) if w is not None]
    except Exception:
        return []


def _charts(widget):
    try:
        return list(widget.findChildren(ZoomableMixin))
    except RuntimeError:
        return []


def _adaptive_state(chart):
    st = getattr(chart, "_adaptive_state", None)
    return st if isinstance(st, dict) else None


def _adaptive_active(chart):
    st = _adaptive_state(chart)
    return bool(st and st.get("active"))


def _leave_adaptive(chart):
    st = _adaptive_state(chart)
    leave = st.get("leave") if st else None
    if callable(leave):
        leave()


def _index_range(rows, d0, d1):
    """Row indexes (first, last) of the dates d0..d1 in rows, or None."""
    first = last = None
    for i, row in enumerate(rows):
        d = _row_date(row)
        if d is None:
            return None
        if first is None and d >= d0:
            first = i
        if d <= d1:
            last = i
    if first is None or last is None or last < first:
        return None
    return first, last


def _target_chart(widget):
    charts = _charts(widget)
    for c in charts:
        if c.isVisible():
            return c
    return charts[0] if charts else None


def attach(manager, widget):
    """Connect the zoom of every chart in widget (safe to call again)."""
    for chart in _charts(widget):
        if getattr(chart, "_zoom_link_attached", False):
            continue
        signal = getattr(chart, "zoom_changed", None)
        if signal is None:
            continue
        chart._zoom_link_attached = True
        chart._zoom_link_manager = manager
        chart._zoom_link_was_adaptive = False
        signal.connect(
            lambda zoomed, start, end, c=chart, m=manager: _on_zoom(m, c, bool(zoomed), int(start), int(end))
        )


def _on_zoom(manager, src, zoomed, start, end):
    global _busy
    if _busy or not is_chart_linked(src):
        return
    try:
        adaptive_now = _adaptive_active(src)
        was_adaptive = bool(getattr(src, "_zoom_link_was_adaptive", False))
        src._zoom_link_was_adaptive = adaptive_now
        if not adaptive_now:
            # Stale callback: an earlier handler already swapped the data.
            if (bool(src._is_zoomed), int(src._zoom_start), int(src._zoom_end)) != (zoomed, start, end):
                return
        dates = None
        if adaptive_now or zoomed:
            dates = zoom_dates(src)
            if dates is None:
                return

        src_widget = _widget_of(manager, src)
        _busy = True
        try:
            for widget in _widgets(manager):
                if widget is src_widget:
                    continue
                target = _target_chart(widget)
                if target is None or not is_chart_linked(target):
                    continue
                _apply(target, dates, was_adaptive and not adaptive_now, src if adaptive_now else None)
        finally:
            _busy = False
    except Exception:
        _busy = False
        log_swallowed()


def propagate_reset(src):
    """Reset the other linked charts after the reset button of src was used.

    The button handlers can block the zoom signal while they reset (the activity chart does),
    so the link cannot rely on the signal for a reset."""
    global _busy
    manager = getattr(src, "_zoom_link_manager", None)
    if manager is None or _busy or not is_chart_linked(src):
        return
    try:
        src_widget = _widget_of(manager, src)
        _busy = True
        try:
            for widget in _widgets(manager):
                if widget is src_widget:
                    continue
                target = _target_chart(widget)
                if target is None or not is_chart_linked(target):
                    continue
                _apply(target, None, False)
        finally:
            _busy = False
    except Exception:
        _busy = False
        log_swallowed()


def _widget_of(manager, chart):
    for widget in _widgets(manager):
        if chart in _charts(widget):
            return widget
    return None


def _follow_inside_adaptive(src, chart):
    """Both charts show the 10-minute view: the zoom inside it is followed by index."""
    st_s, st_c = _adaptive_state(src), _adaptive_state(chart)
    if not st_s or not st_c or st_s.get("dates") != st_c.get("dates"):
        return
    if not getattr(src, "_is_zoomed", False):
        if getattr(chart, "_is_zoomed", False):
            chart.reset_zoom()
        return
    rows_s, rows_c = zoom_rows(src), zoom_rows(chart)
    if not rows_c:
        return
    if len(rows_s) == len(rows_c):
        span = (int(src._zoom_start), int(src._zoom_end))
    else:
        span = remap_zoom(zoom_snapshot(src), rows_c)
    if span and span[1] > span[0] and (int(chart._zoom_start), int(chart._zoom_end)) != span:
        chart.set_zoom_range(span[0], span[1])


def _apply(chart, dates, src_left_adaptive, adaptive_src=None):
    """Bring chart to dates (None means reset)."""
    if _adaptive_active(chart):
        if dates is not None and not src_left_adaptive:
            if adaptive_src is not None:
                _follow_inside_adaptive(adaptive_src, chart)
            return  # already in the 10-minute view
        _leave_adaptive(chart)
        if dates is None:
            if getattr(chart, "_is_zoomed", False):
                chart.reset_zoom()
            return
    if dates is None:
        if getattr(chart, "_is_zoomed", False):
            chart.reset_zoom()
        return
    rows = zoom_rows(chart)
    span = _index_range(rows, dates[0], dates[1]) if rows else None
    if span is None:
        return
    first, last = span
    if first == 0 and last == len(rows) - 1:
        if getattr(chart, "_is_zoomed", False):
            chart.reset_zoom()
        return
    if (int(chart._zoom_start), int(chart._zoom_end)) != (first, last + 1):
        chart.set_zoom_range(first, last + 1)


def is_chart_linked(chart):
    return bool(getattr(chart, "_zoom_linked", True))


def has_charts(widget):
    return bool(_charts(widget))


def is_linked(widget):
    charts = _charts(widget)
    return bool(charts) and all(is_chart_linked(c) for c in charts)


def set_linked(widget, linked):
    for c in _charts(widget):
        c._zoom_linked = bool(linked)


def counts(manager):
    """(linked widgets, disconnected widgets) among the pinned charts."""
    linked = off = 0
    for widget in _widgets(manager):
        if not _charts(widget):
            continue
        if is_linked(widget):
            linked += 1
        else:
            off += 1
    return linked, off


def set_all_linked(manager, linked):
    for widget in _widgets(manager):
        set_linked(widget, linked)
