# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""What can be added to the main screen (charts, stat cards by group, the text widget), how
a new one is pinned, and the "Add Widget..." entry of the right-click menu."""
import copy

from aqt.qt import QAction, QTimer

from .....ui import Period
from .....logic.widget_registry import WidgetRegistry
from ......i18n import tr, N_

CHARTS = (
    ("activity", N_("Activity")),
    ("retention", N_("Retention")),
    ("heatmap", N_("Heatmap")),
    ("added", N_("Added")),
    ("distribution", N_("Distribution")),
    ("card_counts", N_("Card Counts")),
    ("hourly", N_("Hourly Breakdown")),
    ("future_due", N_("Future Due")),
    ("review_intervals", N_("Review Intervals")),
    ("stability", N_("Card Stability")),
    ("difficulty", N_("Card Difficulty")),
    ("retrievability", N_("Card Retrievability")),
)


def chart_groups():
    """[(group name, [(chart type, name)])]: the charts above, then the more detailed ones
    by group (charts.more_charts)."""
    from ....charts.more_charts import CHARTS as MORE_CHARTS

    groups = [(N_("Charts"), list(CHARTS))]
    for metric in MORE_CHARTS:
        names = [g for g, _items in groups]
        if metric.group not in names:
            groups.append((metric.group, []))
        dict(groups)[metric.group].append((metric.widget_type, metric.label))
    return groups

# Config attribute names of the stat cards, by group.
STAT_GROUPS = (
    (N_("Study"), ("DASH_SHOW_TIME", "DASH_SHOW_REVIEWS", "DASH_SHOW_AVG_TIME", "DASH_SHOW_REVIEWS_PER_DAY",
               "DASH_SHOW_REVIEWS_PER_ACTIVE_DAY", "DASH_SHOW_TIME_PER_DAY", "DASH_SHOW_TIME_PER_ACTIVE_DAY",
               "DASH_SHOW_BEST_DAY", "DASH_SHOW_AGAIN")),
    (N_("Retention"), ("DASH_SHOW_RET_ALL", "DASH_SHOW_RET_YOUNG", "DASH_SHOW_RET_MAT", "DASH_SHOW_RET_TRUE",
                   "DASH_SHOW_REV_YOUNG", "DASH_SHOW_REV_MATURE")),
    (N_("Streaks"), ("DASH_SHOW_STREAK", "DASH_SHOW_LONGEST_STREAK", "DASH_SHOW_ACTIVE_DAYS", "DASH_SHOW_DAYS_LEARNED")),
    (N_("Cards"), ("DASH_SHOW_CARDS_TOTAL", "DASH_SHOW_CARDS_NEW", "DASH_SHOW_CARDS_LEARNING", "DASH_SHOW_CARDS_YOUNG",
               "DASH_SHOW_CARDS_MATURE", "DASH_SHOW_CARDS_SUSPENDED", "DASH_SHOW_CARDS_BURIED",
               "DASH_SHOW_CARDS_DELETED")),
    (N_("Schedule and memory"), ("DASH_SHOW_DUE_TODAY", "DASH_SHOW_BACKLOG", "DASH_SHOW_LAPSES",
                             "DASH_SHOW_AVG_RETRIEVABILITY", "DASH_SHOW_AVG_STABILITY")),
)


def default_span(widget_type, stat_key=None):
    """The period a new widget opens on: the past month for a chart (readable daily bars;
    Total is one click away on its label), None for a stat card (it keeps its own default,
    Total) and for a widget without a period."""
    from .card_chips import has_time_span

    if widget_type != "stat_card" and has_time_span({"type": widget_type, "stat_key": stat_key}):
        return Period.MONTH
    return None


class Choice:
    """A widget to add: a chart type, a stat card or a text (with its text)."""

    def __init__(self, widget_type, label, stat_key=None, template=None, saved=None):
        self.widget_type = widget_type
        self.label = label
        self.stat_key = stat_key
        self.template = template
        # A saved widget's definition (saved_widgets): added with all its settings.
        self.saved = saved
        # Set by the widget gallery: the period and decks it is added with (None: defaults).
        self.time_span = None
        self.custom_days = None
        self.deck_ids = None

    @property
    def family(self):
        if self.widget_type == "stat_card":
            return "stat"
        return "text" if self.widget_type == "text_label" else "chart"


def pin_new(manager, choice, after_id=None, fields=None, refresh=True):
    """Pin the choice (after after_id, see WidgetRegistry.add) and return its id."""
    saved = getattr(choice, "saved", None)
    # A saved widget: its settings as they were saved, then its place here (fields)
    extra = {k: v for k, v in copy.deepcopy(saved or {}).items()
             if k not in ("id", "type", "label", "stat_key", "time_span", "custom_days", "deck_ids", "deck_id")}
    extra.update(fields or {})
    if choice.widget_type == "text_label":
        extra["template"] = choice.template or ""
    # The period and decks picked in the widget gallery (see WidgetGallery.fields_for); a saved widget keeps its own
    # period unless one is picked there
    span = getattr(choice, "time_span", None)
    if span is None and saved and saved.get("time_span") is not None:
        span = saved.get("time_span")
        if saved.get("custom_days") is not None:
            extra["custom_days"] = saved.get("custom_days")
    elif span is None:
        span = default_span(choice.widget_type, choice.stat_key)
    elif getattr(choice, "custom_days", None) is not None:
        extra["custom_days"] = choice.custom_days
    if getattr(choice, "deck_ids", None):
        extra["deck_ids"] = list(choice.deck_ids)
    new_id = WidgetRegistry.add(
        choice.widget_type, choice.label, stat_key=choice.stat_key,
        time_span=span, after_id=after_id, **extra,
    )
    if refresh:
        manager.refresh()
    return new_id


def add_widget_actions(menu, manager, icon_fn=None, after_def=None):
    """The "Add Widget..." entry: it opens the widget gallery, and the widget picked goes
    right after the one right clicked (after_def), or in a new box below it when it is of
    another kind (see add_here.add_at)."""
    act = QAction(tr("Add Widget..."), menu)
    if icon_fn is not None:
        act.setIcon(icon_fn("plus"))
    target = None
    if isinstance(after_def, dict) and after_def.get("id"):
        from .....logic.pinned_layout import box_of, family, row_of

        target = {"kind": "after", "id": after_def["id"], "family": family(after_def),
                  "box": box_of(after_def), "row": row_of(after_def)}

    def _open():
        from .add_here import open_gallery_at

        open_gallery_at(manager, target)

    # Opened once the menu has closed (a window opened from inside its loop starts white).
    act.triggered.connect(lambda _=False: QTimer.singleShot(0, _open))
    menu.addAction(act)
    return act
