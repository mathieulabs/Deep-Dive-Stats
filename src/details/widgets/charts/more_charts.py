# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Every chart beyond the usual ones (added to Deep Dive with "+ Add Chart", in their own
groups of the widget gallery), with what their menus offer.

kind: "daily" (charts.daily_metrics, read from the review history of each day),
"intervals" (Interval Load, read from the current intervals of the cards), "cards"
(charts.card_history, the cards counted by their lapses / reviews / learning answers),
"week" (charts.week_hours, the reviews of the period by weekday and hour), "today"
(charts.due_today, the learning cards due today by hour) or "first_today" (First Answer Retention:
the first answer of each card on each day of the period; web only) or "memory"
(Stability / Difficulty Time Machine: the cards' FSRS memory states on a past day; web only) or "sxr" (SxR
Heatmap: the review cards now by stability and retrievability, logic.metrics.sxr; web only)."""

from .daily_metrics import CHARTS as _DAILY
from ....i18n import N_


class MoreChart:
    def __init__(self, widget_type, label, group, kind, average=True, cumulative=False, has_span=True, percent=False):
        self.percent = percent  # "Show as %" in its menu (shares of each bar)
        self.widget_type = widget_type
        self.label = label
        self.group = group
        self.kind = kind
        self.average = average  # average line and "on active days" in its menu
        self.cumulative = cumulative  # running total in its menu
        self.has_span = has_span  # a period (the intervals are the cards' current ones: none)


CHARTS = tuple(
    [MoreChart(m.widget_type, m.label, m.group, "daily", average=m.average, cumulative=m.cumulative,
               percent=m.percent, has_span=m.has_span) for m in _DAILY]
    + [MoreChart("week_hours", N_("Week by Hour"), N_("Ratings and time"), "week", average=False)]
    + [MoreChart("interval_load", N_("Interval Load"), N_("Load and due"), "intervals",
                 average=False, cumulative=True, has_span=False)]
    + [MoreChart("due_today", N_("Due Today by Hour"), N_("Load and due"), "today",
                 average=False, cumulative=True, has_span=False)]
    + [MoreChart("todays_retention", N_("First Answer Retention"), N_("Ratings and time"), "first_today",
                 average=False)]
    + [MoreChart("lapse_distribution", N_("Lapses per Card"), N_("Card history"), "cards",
                 average=False, cumulative=True, has_span=False),
       MoreChart("review_distribution", N_("Reviews per Card"), N_("Card history"), "cards",
                 average=False, cumulative=True, has_span=False),
       MoreChart("learning_steps", N_("Learning Steps per Card"), N_("Card history"), "cards",
                 average=False, cumulative=True, has_span=False),
       # The cards by the time spent on them over all their reviews.
       MoreChart("time_distribution", N_("Time per Card"), N_("Card history"), "cards",
                 average=False, cumulative=True, has_span=False),
       # The review cards by their interval on a past day, on the first day of the period chosen.
       MoreChart("interval_history", N_("Interval Time Machine"), N_("Card history"), "cards",
                 average=False, cumulative=True)]
    # Card Stability / Card Difficulty on the first day of the period chosen (Anki's memory states
    # after each review: logic.metrics.fsrs_history)
    + [MoreChart("stability_history", N_("Stability Time Machine"), N_("Card history"), "memory",
                 average=False, cumulative=True),
       MoreChart("difficulty_history", N_("Difficulty Time Machine"), N_("Card history"), "memory",
                 average=False)]
    # How the cards were recalled after their first rating, by that rating, with a FSRS curve fitted to each
    # (logic.metrics.first_curves)
    + [MoreChart("first_forgetting", N_("First Long-term Forgetting Curve"), N_("Card history"), "curve",
                 average=False, has_span=False),
       MoreChart("first_forgetting_short", N_("First Short-term Forgetting Curve"), N_("Card history"), "curve",
                 average=False, has_span=False)]
    # The review cards now by their FSRS stability and retrievability
    + [MoreChart("sxr_heatmap", N_("SxR Heatmap"), N_("Card history"), "sxr", average=False, has_span=False)]
    # FSRS's predicted recall against the real one, by stability and difficulty
    + [MoreChart("bw_matrix", N_("B-W Matrix"), N_("Ratings and time"), "bw", average=False, has_span=False)]
    # The cards of the user's own searches, a slice each
    + [MoreChart("custom_pie", N_("Custom Pie"), N_("Card history"), "custom", average=False, has_span=False)]
)
BY_TYPE = {c.widget_type: c for c in CHARTS}
TYPES = tuple(BY_TYPE)
AVERAGE_TYPES = tuple(c.widget_type for c in CHARTS if c.average)
CUMULATIVE_TYPES = tuple(c.widget_type for c in CHARTS if c.cumulative)
NO_SPAN_TYPES = tuple(c.widget_type for c in CHARTS if not c.has_span)
PERCENT_TYPES = tuple(c.widget_type for c in CHARTS if c.percent)
