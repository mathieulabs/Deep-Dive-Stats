# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Add Widget submenu of the pinned context menu: pin a chart, stat card or text
without opening the Deep Dive window."""
from aqt.qt import QAction

from ..imports import Config
from ...store.registry import WidgetRegistry
from ....stats_cards.logic.model import get_stat_card_default_title

CHARTS = (
    ("activity", "Activity"),
    ("retention", "Retention"),
    ("heatmap", "Heatmap"),
    ("added", "Added"),
    ("distribution", "Distribution"),
    ("card_counts", "Card Counts"),
    ("hourly", "Hourly Breakdown"),
    ("future_due", "Future Due"),
    ("review_intervals", "Review Intervals"),
    ("stability", "Card Stability"),
    ("difficulty", "Card Difficulty"),
    ("retrievability", "Card Retrievability"),
)

# Config attribute names of the stat cards, by group.
STAT_GROUPS = (
    ("Study", ("DASH_SHOW_TIME", "DASH_SHOW_REVIEWS", "DASH_SHOW_AVG_TIME", "DASH_SHOW_REVIEWS_PER_DAY",
               "DASH_SHOW_TIME_PER_DAY", "DASH_SHOW_BEST_DAY", "DASH_SHOW_AGAIN")),
    ("Retention", ("DASH_SHOW_RET_ALL", "DASH_SHOW_RET_YOUNG", "DASH_SHOW_RET_MAT", "DASH_SHOW_RET_TRUE",
                   "DASH_SHOW_REV_YOUNG", "DASH_SHOW_REV_MATURE")),
    ("Streaks", ("DASH_SHOW_STREAK", "DASH_SHOW_LONGEST_STREAK", "DASH_SHOW_ACTIVE_DAYS", "DASH_SHOW_DAYS_LEARNED")),
    ("Cards", ("DASH_SHOW_CARDS_TOTAL", "DASH_SHOW_CARDS_NEW", "DASH_SHOW_CARDS_LEARNING", "DASH_SHOW_CARDS_YOUNG",
               "DASH_SHOW_CARDS_MATURE", "DASH_SHOW_CARDS_SUSPENDED", "DASH_SHOW_CARDS_BURIED",
               "DASH_SHOW_CARDS_DELETED")),
    ("Schedule and memory", ("DASH_SHOW_DUE_TODAY", "DASH_SHOW_BACKLOG", "DASH_SHOW_LAPSES",
                             "DASH_SHOW_AVG_RETRIEVABILITY", "DASH_SHOW_AVG_STABILITY")),
)


def stat_groups_by_key():
    """(group names in order, {stat config key: group name})."""
    names = [group for group, _ in STAT_GROUPS]
    by_key = {}
    for group, attrs in STAT_GROUPS:
        for attr in attrs:
            key = getattr(Config, attr, None)
            if key is not None:
                by_key[key] = group
    return names, by_key


# Charts over time open on the past month: readable daily bars. Total is one click away.
_DEFAULT_SPANS = {"activity": 2, "added": 2, "retention": 2}


def _pin(manager, widget_type, label, stat_key=None):
    WidgetRegistry.add(widget_type, label, stat_key=stat_key, time_span=_DEFAULT_SPANS.get(widget_type))
    manager._last_state = None
    manager._last_widget_set = None
    manager.refresh()


def add_widget_actions(menu, manager, add_text_fn, icon_fn=None):
    """Add an "Add Widget" submenu: Charts, Stat cards (by group) and Text Widget."""
    sub = menu.addMenu("Add Widget")
    if icon_fn is not None:
        sub.setIcon(icon_fn("plus"))

    charts = sub.addMenu("Chart")
    for wtype, label in CHARTS:
        act = QAction(label, charts)
        act.triggered.connect(lambda _=False, t=wtype, lb=label: _pin(manager, t, lb))
        charts.addAction(act)

    from ....stats_cards.core.menu_search import MenuSearch

    stats = sub.addMenu("Stat card")
    search = MenuSearch(stats)
    for group, names in STAT_GROUPS:
        gmenu = stats.addMenu(group)
        search.add_group(gmenu)
        for name in names:
            key = getattr(Config, name, None)
            if key is None:
                continue
            label = get_stat_card_default_title(key)
            act = QAction(label, gmenu)
            act.triggered.connect(lambda _=False, k=key, lb=label: _pin(manager, "stat_card", lb, stat_key=k))
            gmenu.addAction(act)
            flat = QAction(label, stats)
            flat.triggered.connect(lambda _=False, k=key, lb=label: _pin(manager, "stat_card", lb, stat_key=k))
            search.add_result(label, flat)
    search.finish()

    sub.addSeparator()
    text_act = QAction("Text Widget...", sub)
    text_act.triggered.connect(lambda _=False: add_text_fn())
    sub.addAction(text_act)
    return sub
