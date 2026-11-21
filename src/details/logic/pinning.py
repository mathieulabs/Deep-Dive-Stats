# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Pinning a Deep Dive chart to the main screen ("Pin ... to main menu"), without any window: which charts can be
pinned, under what name, and the pin itself. Used by the Deep Dive window (web_ui/window.py)."""

from __future__ import annotations

# The Deep Dive's own charts that have a pinned widget of the same type (the extra charts all have one).
PINNABLE = (
    "activity", "retention", "added", "distribution", "card_counts", "heatmap", "hourly",
    "future_due", "review_intervals", "stability", "difficulty", "retrievability",
)


def pin_info(wtype):
    """(widget type, label) of the chart a section shows, or None if it cannot be pinned."""
    from ..widgets.charts.more_charts import BY_TYPE

    if wtype in BY_TYPE:
        return wtype, BY_TYPE[wtype].label
    if wtype not in PINNABLE:
        return None
    from ..ui.config.widgets.label_defaults import DEFAULT_LABELS

    return wtype, DEFAULT_LABELS.get(wtype, wtype.replace("_", " ").title())


# A chart and its Time Machine, the same chart on a past day (View on a Past Day; app.js DD.pastOf)
PAST = {"review_intervals": "interval_history", "stability": "stability_history", "difficulty": "difficulty_history"}


def add_pin(wtype, label, deck_id=None, span=-1, after_id=None):
    """The widget added to the main screen (its deck's name after the label when it reads one deck), right after
    after_id's when given; its id."""
    from aqt import mw

    from ..widgets.pinned import WidgetRegistry
    from ..widgets.pinned.main_menu.manager import MainMenuWidgetManager

    if deck_id is not None:
        deck = mw.col.decks.get(deck_id)
        if deck:
            label = f"{label} ({deck['name']})"
    wid = WidgetRegistry.add(wtype, label, deck_id=deck_id, time_span=span, after_id=after_id)
    MainMenuWidgetManager.instance().refresh()
    return wid


def pin_chart(wtype, span=-1):
    """Pin a Deep Dive chart on its period; False when it cannot be pinned."""
    info = pin_info(wtype)
    if info is None:
        return False
    add_pin(info[0], info[1], None, int(span))
    return True


def pin_past(widget_id):
    """View on a Past Day on the main screen: the Time Machine of a pinned chart, pinned right after it on the same
    deck and period. {id, added}: the new one, or the one already pinned there (nothing added); None without one."""
    from ..widgets.pinned import WidgetRegistry

    src = next((w for w in WidgetRegistry.get_all() if str(w.get("id")) == str(widget_id)), None)
    past = PAST.get((src or {}).get("type"))
    if past is None:
        return None
    deck_id, span = src.get("deck_id"), src.get("time_span")

    def same(a, b):
        return (None if a is None else int(a)) == (None if b is None else int(b))

    for w in WidgetRegistry.get_all():
        if w.get("type") == past and same(w.get("deck_id"), deck_id) and same(w.get("time_span"), span):
            return {"id": w.get("id"), "added": False}
    return {"id": add_pin(past, pin_info(past)[1], deck_id, span, after_id=src.get("id")), "added": True}
