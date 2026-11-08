# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Charts of the cards as they are now, counted by a number each card carries: its lapses
(times forgotten), its reviews, or the learning answers it needed before graduating. A bar
is how many cards have that number.

Lapses and reviews: one GROUP BY on the cards table, kept until the collection changes.
Learning steps: from the review history (logic.metrics.learning_steps)."""

from aqt import mw

from ..review_intervals import ReviewIntervalsChart
from ...chart_utils.formatting import fmt_num, fmt_num_trim_zeros
from .....i18n import tr, tr_n

FIELDS = {"lapse_distribution": "lapses", "review_distribution": "reps"}
_cache = {}


def _did_limit(cfg, deck_id):
    from ....logic.history_provider import HistoryProvider

    return HistoryProvider._get_did_limit(cfg, deck_id)


def card_distribution(cfg, deck_id, widget_type):
    """{"distribution": {n: cards}, "total": cards, "zero": cards at 0, "sum": sum of n} of the
    cards already studied (not new) of the decks; n >= 1 in the distribution."""
    if deck_id == -1 or getattr(mw, "col", None) is None:
        return {"distribution": {}, "total": 0, "zero": 0, "sum": 0}
    if widget_type == "learning_steps":
        from ....logic.metrics.learning_steps import learning_distribution

        return learning_distribution(cfg, deck_id)
    field = FIELDS[widget_type]
    try:
        key = (widget_type, repr(deck_id), mw.col.mod, mw.col.sched.today)
    except Exception:
        key = None
    if key is not None and key in _cache:
        return _cache[key]
    limit = _did_limit(cfg, deck_id)
    rows = mw.col.db.all(
        f"SELECT cards.{field}, COUNT(*) FROM cards AS cards WHERE cards.type > 0 {limit} GROUP BY cards.{field}")
    dist = {int(n): int(c) for n, c in rows if n is not None and int(n) > 0}
    zero = sum(int(c) for n, c in rows if n is not None and int(n) <= 0)
    out = {"distribution": dist, "total": sum(dist.values()) + zero, "zero": zero,
           "sum": sum(n * c for n, c in dist.items())}
    if key is not None:
        if len(_cache) > 64:
            _cache.clear()
        _cache[key] = out
    return out


class CardCountChart(ReviewIntervalsChart):
    """Cards by number of lapses / reviews (the Review Intervals chart, other words)."""

    def __init__(self, widget_type, data_dict, parent=None, adaptive_binning=True, filter_mode="95_percent"):
        self.widget_type = widget_type
        self._source = dict(data_dict or {})
        super().__init__(self._source, parent=parent, adaptive_binning=adaptive_binning, filter_mode=filter_mode)

    def update_data(self, new_data, adaptive_binning=None, transition_mode=None):
        self._source = dict(new_data or {})
        return super().update_data(self._source, adaptive_binning=adaptive_binning, transition_mode=transition_mode)

    def _count_text(self, n):
        if self.widget_type == "lapse_distribution":
            return tr_n("{count} lapse", "{count} lapses", n, count=n)
        if self.widget_type == "learning_steps":
            return tr_n("{count} learning review", "{count} learning reviews", n, count=n)
        return tr_n("{count} review", "{count} reviews", n, count=n)

    def get_tooltip_text(self, idx, points_count):
        day, next_day = self._day_range(idx, points_count)
        cards = sum(self.filtered_dist.get(d, 0) for d in range(day, next_day))
        what = self._count_text(day) if next_day - day <= 1 else f"{day}-{next_day - 1}"
        text = tr("{name}: {value}", name=what,
                  value=tr_n("{count} card", "{count} cards", cards, count=fmt_num(cards)))
        if getattr(self, "cumulative_visible", True):
            first, _ = self._day_range(0, points_count)
            running = sum(self.filtered_dist.get(d, 0) for d in range(first, next_day))
            text += "\n" + tr_n("Total: {count} card", "Total: {count} cards", running, count=fmt_num(running))
        return text

    def get_stats_text(self):
        total = int(self._source.get("total", 0) or 0)
        if total <= 0:
            return []
        if self.widget_type == "learning_steps":
            # The average of the cards that went through learning; the others (graduated
            # without a learning answer: given a due date, imported) said apart.
            learned = total - int(self._source.get("zero", 0) or 0)
            avg = float(self._source.get("sum", 0) or 0) / max(1, learned)
            out = [tr("Avg: {value}", value=self._count_text_avg(avg))] if learned else []
            skipped = int(self._source.get("zero", 0) or 0)
            if skipped:
                out.append(tr_n("Without learning: {count} card", "Without learning: {count} cards",
                                skipped, count=fmt_num(skipped)))
            return out
        avg = float(self._source.get("sum", 0) or 0) / total
        out = [tr("Avg: {value}", value=self._count_text_avg(avg))]
        if self.widget_type == "lapse_distribution":
            never = int(self._source.get("zero", 0) or 0)
            out.append(tr("Never forgotten: {value}%", value=fmt_num_trim_zeros(never * 100.0 / total, 1)))
        return out

    def _count_text_avg(self, v):
        text = fmt_num_trim_zeros(v, 1)
        if self.widget_type == "lapse_distribution":
            return tr_n("{count} lapse", "{count} lapses", v, count=text)
        if self.widget_type == "learning_steps":
            return tr_n("{count} learning review", "{count} learning reviews", v, count=text)
        return tr_n("{count} review", "{count} reviews", v, count=text)
