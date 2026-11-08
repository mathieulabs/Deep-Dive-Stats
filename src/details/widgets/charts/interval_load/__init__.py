# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Interval Load: how many reviews a day the cards of each interval bring.

A card with an interval of d days comes back about once every d days: it adds 1/d review
to each day. The chart is the Review Intervals chart with that load instead of the card
count (the sum of the bars is the daily load of the deck)."""

from ..review_intervals import ReviewIntervalsChart
from ...chart_utils.formatting import fmt_num_trim_zeros
from .....i18n import tr, tr_n


def to_load(data):
    """The review intervals data (distribution {interval: cards}) as load {interval: reviews/day}."""
    data = dict(data or {})
    dist = data.get("distribution") or {}
    load = {}
    for ivl, count in dist.items():
        try:
            d = int(ivl)
        except (TypeError, ValueError):
            continue
        if d >= 1 and count:
            load[d] = float(count) / d
    return {"distribution": load, "total": data.get("total", 0)}


def _per_day(value):
    v = float(value or 0.0)
    text = fmt_num_trim_zeros(v, 1 if v < 10 else 0)
    return tr("{value}/day", value=tr_n("{count} review", "{count} reviews", v, count=text))


class IntervalLoadChart(ReviewIntervalsChart):
    def __init__(self, data_dict, parent=None, adaptive_binning=True, filter_mode="95_percent"):
        super().__init__(to_load(data_dict), parent=parent, adaptive_binning=adaptive_binning,
                         filter_mode=filter_mode)

    def update_data(self, new_data, adaptive_binning=None, transition_mode=None):
        return super().update_data(to_load(new_data), adaptive_binning=adaptive_binning,
                                   transition_mode=transition_mode)

    def get_tooltip_text(self, idx, points_count):
        day, next_day = self._day_range(idx, points_count)
        load = sum(self.filtered_dist.get(d, 0) for d in range(day, next_day))
        days = f"{day}-{next_day - 1}" if next_day - day > 1 else day
        text = tr("Interval {days} days: {value}", days=days, value=_per_day(load))
        if getattr(self, "cumulative_visible", True):
            first, _ = self._day_range(0, points_count)
            running = sum(self.filtered_dist.get(d, 0) for d in range(first, next_day))
            text += "\n" + tr("Total: {value}", value=_per_day(running))
        return text

    def get_stats_text(self):
        total = sum(float(v or 0) for v in (self.data_dict.get("distribution") or {}).values())
        if total <= 0:
            return []
        return [tr("Daily load: {value}", value=_per_day(total))]
