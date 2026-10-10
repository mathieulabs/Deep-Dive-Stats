# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Click a chart bar or slice to show its cards in the Anki browser (like native Anki stats)."""
from aqt.qt import QEvent, QObject, Qt
from ...logic.logger import log_swallowed

_CLICK_SLOP = 5

_PIE_QUERIES = {
    "new": "is:new -is:suspended -is:buried",
    "learn": "is:learn -is:review -is:suspended -is:buried",
    "relearn": "is:learn is:review -is:suspended -is:buried",
    "young": "is:review -is:learn prop:ivl<21 -is:suspended -is:buried",
    "mature": "is:review -is:learn prop:ivl>=21 -is:suspended -is:buried",
    "suspended": "is:suspended",
    "buried": "is:buried",
}


def resolve_deck(chart):
    """Deck selection of a chart: pinned widgets carry it, Deep Dive charts use the open row."""
    w = chart
    while w is not None:
        if getattr(w, "_bc_deck_set", False):
            return w._bc_deck
        w = w.parentWidget()
    try:
        mgr = getattr(chart.window(), "deep_dive_manager", None)
        row = getattr(mgr, "last_row_data", None) or {}
        if row.get("is_deleted"):
            return -1
        return row.get("did")
    except Exception:
        return None


def set_pinned_deck(widget, deck_id):
    """Called by the pinned widget factory so charts know which deck they show."""
    try:
        widget._bc_deck_set = True
        widget._bc_deck = deck_id
    except Exception:
        log_swallowed()


def _kinds(chart):
    return {c.__name__ for c in type(chart).__mro__}


def _target(chart):
    """Return a callable that opens the browser for the hovered item, or None."""
    from ...logic.interactions import browser_search as bs
    kinds = _kinds(chart)
    deck = resolve_deck(chart)

    if "PieChartWidget" in kinds:
        key = getattr(chart, "_hover_key", None)
        if key == "deleted":
            return lambda: bs._tip("Deleted cards cannot be shown in the browser")
        q = _PIE_QUERIES.get(key)
        return (lambda: bs.open_query(q, deck)) if q else None

    idx = getattr(chart, "hover_index", -1)
    if idx is None or idx < 0:
        return None

    if "ActivityStackedChart" in kinds or "AddedChartWidget" in kinds:
        data = chart._get_display_data()
        if idx >= len(data):
            return None
        label = data[idx].get("pretty_date", "")
        kind = "added" if "AddedChartWidget" in kinds else "reviewed"
        return lambda: bs.open_cards_for_label(kind, label, deck) or bs._tip("No date for this bar")

    if "HourlyBreakdownChart" in kinds:
        span = getattr(chart, "_bc_span", None)
        if span is None:
            return None
        return lambda: bs.open_cards_for_hour(idx, span, deck)

    if "RetentionChart" in kinds:
        data = chart._get_display_data() or {}
        label = ""
        for series in data.values():
            if series:
                if idx < len(series) and isinstance(series[idx], (list, tuple)):
                    label = str(series[idx][0])
                break
        return lambda: bs.open_cards_for_label("reviewed", label, deck) or bs._tip("No date for this bar")

    if "ActivityChart" in kinds:
        labels = chart._get_labels()
        if idx >= len(labels):
            return None
        label = labels[idx]
        return lambda: bs.open_cards_for_label("reviewed", label, deck) or bs._tip("No date for this bar")

    if "FutureDueChart" in kinds:
        a, b = chart._get_bin_day_range(idx, chart._get_points_count())
        return lambda: bs.open_query(f"prop:due>={a} prop:due<{b}", deck)

    if "ReviewIntervalsChart" in kinds:
        a, b = chart._day_range(idx, chart._get_points_count())
        return lambda: bs.open_query(f"prop:ivl>={a} prop:ivl<{b}", deck)

    if "StabilityChartWidget" in kinds:
        k, _v = chart.data_list[idx]
        from .binning import get_bin_size
        bs_ = get_bin_size(chart.max_days) if chart.binning_active else 1
        hi = k + max(1, bs_)
        return lambda: bs.open_query(f"prop:s>={k} prop:s<{hi}", deck)

    if "DifficultyChartWidget" in kinds or "RetrievabilityChartWidget" in kinds:
        k, _v = chart.data_list[idx]
        prop = "d" if "DifficultyChartWidget" in kinds else "r"
        lo, hi = k / 100.0, (k + 1) / 100.0
        return lambda: bs.open_query(f"prop:{prop}>={lo:g} prop:{prop}<{hi:g}", deck)

    return None


class _ClickFilter(QObject):
    def __init__(self, chart):
        super().__init__(chart)
        self._chart = chart
        self._press = None

    def eventFilter(self, obj, event):
        t = event.type()
        if t == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self._press = event.pos()
        elif t == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            p, self._press = self._press, None
            if p is not None and (event.pos() - p).manhattanLength() <= _CLICK_SLOP:
                try:
                    act = _target(self._chart)
                    if act is not None:
                        act()
                except Exception as e:
                    from ...logic.logger import log_error
                    log_error(f"browser click failed: {e}")
        return False


_CLICKABLE = {
    "PieChartWidget", "ActivityStackedChart", "AddedChartWidget", "ActivityChart",
    "FutureDueChart", "ReviewIntervalsChart", "StabilityChartWidget",
    "DifficultyChartWidget", "RetrievabilityChartWidget", "HourlyBreakdownChart", "RetentionChart",
}


def install_browser_click(chart):
    if not (_kinds(chart) & _CLICKABLE):
        return
    if getattr(chart, "_bc_installed", False):
        return
    chart._bc_installed = True
    chart._bc_filter = _ClickFilter(chart)
    chart.installEventFilter(chart._bc_filter)
