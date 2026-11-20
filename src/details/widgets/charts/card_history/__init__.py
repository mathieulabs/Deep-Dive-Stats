# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Charts of the cards as they are now, counted by a number each card carries: its lapses
(times forgotten), its reviews, the learning answers it needed before graduating, or the
seconds spent on it over all its reviews. A bar is how many cards have that number.

Lapses and reviews: one GROUP BY on the cards table, kept until the collection changes.
Learning steps and time: from the review history (logic.metrics.learning_steps, card_time)."""

from aqt import mw

FIELDS = {"lapse_distribution": "lapses", "review_distribution": "reps"}
_cache = {}


def _did_limit(cfg, deck_id):
    from ....logic.history_provider import HistoryProvider

    return HistoryProvider._get_did_limit(cfg, deck_id)


def card_distribution(cfg, deck_id, widget_type, suspended=True):
    """{"distribution": {n: cards}, "total": cards, "zero": cards at 0, "sum": sum of n} of the
    cards already studied (not new) of the decks; n >= 1 in the distribution. Lapses and reviews
    also carry "load" {n: reviews a day} and "load_zero" (see measured). suspended=False: the
    suspended cards left out (Include Suspended off)."""
    where = "" if suspended else " AND cards.queue != -1"
    if deck_id == -1 or getattr(mw, "col", None) is None:
        return {"distribution": {}, "total": 0, "zero": 0, "sum": 0}
    if widget_type == "learning_steps":
        from ....logic.metrics.learning_steps import learning_distribution

        return learning_distribution(cfg, deck_id, where)
    if widget_type == "time_distribution":
        from ....logic.metrics.card_time import time_distribution

        return time_distribution(cfg, deck_id, where)
    if widget_type == "interval_history":
        return interval_history(cfg, deck_id)
    field = FIELDS[widget_type]
    try:
        key = (widget_type, repr(deck_id), mw.col.mod, mw.col.sched.today, bool(suspended))
    except Exception:
        key = None
    if key is not None and key in _cache:
        return _cache[key]
    from ....logic.metrics.review_intervals import INTERVAL_CARDS_COND

    limit = _did_limit(cfg, deck_id) + where
    # the load of the cards of each number too (1 / interval of the review cards, as Interval Load)
    rows = mw.col.db.all(
        f"SELECT cards.{field}, COUNT(*), TOTAL(CASE WHEN {INTERVAL_CARDS_COND} THEN 1.0 / cards.ivl ELSE 0 END) "
        f"FROM cards AS cards WHERE cards.type > 0 {limit} GROUP BY cards.{field}")
    dist = {int(n): int(c) for n, c, _l in rows if n is not None and int(n) > 0}
    zero = sum(int(c) for n, c, _l in rows if n is not None and int(n) <= 0)
    load = {int(n): float(l) for n, _c, l in rows if n is not None and int(n) > 0 and l}
    out = {"distribution": dist, "total": sum(dist.values()) + zero, "zero": zero,
           "sum": sum(n * c for n, c in dist.items()), "load": load,
           "load_zero": sum(float(l or 0) for n, _c, l in rows if n is not None and int(n) <= 0)}
    if key is not None:
        if len(_cache) > 64:
            _cache.clear()
        _cache[key] = out
    return out


def leech_count(cfg, deck_id, suspended=True):
    """(cards at or over the leech threshold of their deck's preset, that threshold or None when the decks'
    presets differ) of the cards already studied; a card in a filtered deck goes by its home deck."""
    if deck_id == -1 or getattr(mw, "col", None) is None:
        return 0, None
    try:
        key = ("leeches", repr(deck_id), mw.col.mod, bool(suspended))  # (kept as card_distribution)
    except Exception:
        key = None
    if key is not None and key in _cache:
        return _cache[key]
    out = _leech_count(cfg, deck_id, suspended)
    if key is not None:
        if len(_cache) > 64:
            _cache.clear()
        _cache[key] = out
    return out


def _leech_count(cfg, deck_id, suspended):
    where = "" if suspended else " AND cards.queue != -1"
    rows = mw.col.db.all(
        "SELECT CASE WHEN cards.odid != 0 THEN cards.odid ELSE cards.did END AS home, cards.lapses, COUNT(*) "
        f"FROM cards AS cards WHERE cards.type > 0 AND cards.lapses > 0 {_did_limit(cfg, deck_id)}{where} "
        "GROUP BY home, cards.lapses")
    limits, n = {}, 0
    for did, lapses, count in rows:
        if did not in limits:
            try:
                limits[did] = int(mw.col.decks.config_dict_for_deck_id(did)["lapse"]["leechFails"])
            except Exception:
                limits[did] = 8
        if limits[did] > 0 and int(lapses) >= limits[did]:
            n += int(count)
    shown = set(limits.values())
    if not shown:
        try:
            did = deck_id if isinstance(deck_id, int) and deck_id > 0 else mw.col.decks.current()["id"]
            shown = {int(mw.col.decks.config_dict_for_deck_id(did)["lapse"]["leechFails"])}
        except Exception:
            shown = set()
    return n, (shown.pop() if len(shown) == 1 else None)


def interval_history(cfg, deck_id, span=None, custom_days=7):
    """Interval Time Machine: the review cards by their interval on the first day of the period
    `span` (card_states.span_ordinal); today without one (Total)."""
    from .....const.base import Period
    from ....logic.metrics.card_states import intervals_at, span_ordinal

    return intervals_at(cfg, deck_id, False, span_ordinal(Period.TOTAL if span is None else span, custom_days))


MEASURES = ("count", "total", "load")  # what a bar sums: cards, their lapses / reviews, their load


def measured(data, measure):
    """The distribution of card_distribution as another measure: "total" the lapses / reviews of
    the cards of each number (n x cards), "load" their reviews a day (sum of 1 / interval)."""
    data = dict(data or {})
    if measure == "total":
        data["distribution"] = {n: n * c for n, c in (data.get("distribution") or {}).items()}
    elif measure == "load":
        data["distribution"] = dict(data.get("load") or {})
    data["measure"] = measure if measure in MEASURES else "count"
    return data
