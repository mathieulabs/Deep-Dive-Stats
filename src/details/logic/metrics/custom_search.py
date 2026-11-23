# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Custom Pie / Custom Bar: the user's own searches, as in the browser.

searches(raw): the searches a chart's setting holds, cleaned up ([{"q": search, "c": colour or ""}],
at most MAX; the defaults when it holds none), and colour(i, c) the colour of the i-th.
matching(cfg, deck, deleted, queries): for each search, the ids of the deck's cards it finds (a set),
or None when Anki cannot read it; kept until a card changes.
pie_values(...): the value of each search's cards (cards, load, lapses, reviews), or None.
bar_counts(...): each search's reviews and their time in each row of days."""

import threading

from aqt import mw

from ..history_provider.ops.context_fsrs import _col_mod
from .review_buckets import _memo, did_limit as _did_limit, range_from_days

MAX = 8
DEFAULT = ({"q": "is:new", "c": ""}, {"q": "is:review prop:ivl<21", "c": ""}, {"q": "prop:ivl>=21", "c": ""})
COLORS = ("#5b8def", "#e5484d", "#30a46c", "#f5a524", "#8e4ec6", "#12a594", "#e93d82", "#978365")
PIE_MEASURES = ("cards", "load", "lapses", "reviews")

_CACHE = {}
_LOCK = threading.Lock()


def searches(raw):
    out = []
    for s in raw if isinstance(raw, (list, tuple)) else DEFAULT:
        if isinstance(s, str):
            s = {"q": s}
        if not isinstance(s, dict):
            continue
        c = str(s.get("c") or "").strip()
        out.append({"q": str(s.get("q") or "").strip()[:500], "c": c if c.startswith("#") and len(c) in (4, 7) else ""})
        if len(out) >= MAX:
            break
    return out


def colour(i, c=""):
    return c or COLORS[i % len(COLORS)]


def _kept(key, make):
    with _LOCK:
        hit = _CACHE.get(key)
    if hit is not None:
        return hit
    value = make()
    with _LOCK:
        if len(_CACHE) >= 24:
            _CACHE.clear()
        _CACHE[key] = value
    return value


def _deck_cards(limit):
    """{card id: (interval, lapses, reviews)} of the deck's cards."""
    return {int(cid): (int(ivl or 0), int(lapses or 0), int(reps or 0)) for cid, ivl, lapses, reps in
            mw.col.db.all(f"SELECT cards.id, cards.ivl, cards.lapses, cards.reps FROM cards WHERE 1 = 1 {limit}")}


def matching(addon_config, deck_id, is_deleted, queries):
    """([set of card ids, or None for a search Anki cannot read] per search, {card id: (ivl, lapses, reps)})."""
    if deck_id == -1 or is_deleted:
        return [set() for _q in queries], {}  # (the browser finds no deleted card)
    limit = _did_limit(addon_config, deck_id, is_deleted)

    def make():
        cards = _deck_cards(limit)
        sets = []
        for q in queries:
            if not q:
                sets.append(set(cards))
                continue
            try:
                found = mw.col.find_cards(q)
            except Exception:
                sets.append(None)
                continue
            sets.append({int(c) for c in found if int(c) in cards})
        return sets, cards
    return _kept(("match", limit, tuple(queries), _col_mod()), make)


def pie_values(addon_config, deck_id, is_deleted, queries, measure="cards"):
    """The value of each search's cards (None: a search Anki cannot read): their number, their load
    (reviews a day: 1 / interval of each card with one), their lapses or their reviews."""
    sets, cards = matching(addon_config, deck_id, is_deleted, queries)
    out = []
    for found in sets:
        if found is None:
            out.append(None)
        elif measure == "load":
            out.append(sum(1.0 / cards[c][0] for c in found if cards[c][0] > 0))
        elif measure == "lapses":
            out.append(float(sum(cards[c][1] for c in found)))
        elif measure == "reviews":
            out.append(float(sum(cards[c][2] for c in found)))
        else:
            out.append(float(len(found)))
    return out


def bar_counts(sets, days, row_of):
    """[(reviews, time in ms) per search] per row of days: the answers (Learn, Review, Relearn,
    Filtered, not manual) of each search's cards (a card in two searches counts in both).

    Summed in SQL by slot of time (15 minutes; a minute for Today / Yesterday's bins of minutes),
    each slot then put in its row: a row's edges (the day's start at the rollover hour, in a time
    zone a whole number of quarter hours from UTC; a bin's minute) are a slot's. All the period's
    answers read row by row into Python (~100,000 for a big collection) held Python's lock while
    they were decoded, and Anki's window stalled ~600 ms while Deep Dive loaded."""
    rng = range_from_days(days)
    if not rng:
        return [[[0, 0] for _s in sets] for _d in days]
    slot = 60000 if any(len(str(d.get("date", "") or "")) > 10 for d in days or []) else 900000
    # kept until the history changes (review_buckets._memo), by the cards of each search and the rows
    key = ("custom_bar", tuple(None if s is None else hash(frozenset(s)) for s in sets), int(rng[0]), int(rng[1]), slot,
           tuple(str(d.get("date") or d.get("pretty_date") or "") for d in days))
    out = _memo(key, lambda: _bar_counts(sets, days, row_of, rng, slot))
    return [[list(c) for c in r] for r in out]  # (a copy: the kept rows are never changed)


def _bar_counts(sets, days, row_of, rng, slot):
    from ....utils import excluded_days_clause

    excl = excluded_days_clause()
    join = "LEFT JOIN cards ON revlog.cid = cards.id" if "cards." in (excl or "") else ""
    rows = [[[0, 0] for _s in sets] for _d in days]
    rows_of = {}
    for i, found in enumerate(sets):
        if not found:
            continue
        cids = [str(int(c)) for c in found]
        for start in range(0, len(cids), 500):
            ids = ",".join(cids[start:start + 500])
            for b, n, ms in mw.col.db.all(f"""
                    SELECT revlog.id / {slot}, count(), sum(revlog.time) FROM revlog {join}
                    WHERE revlog.id >= {int(rng[0])} AND revlog.id < {int(rng[1])} AND revlog.type < 4 AND revlog.ease BETWEEN 1 AND 4
                      {excl} AND revlog.cid IN ({ids})
                    GROUP BY revlog.id / {slot}"""):
                b = int(b)
                r = rows_of.get(b, -1)
                if r == -1:
                    r = rows_of[b] = row_of(b * slot)
                if r is None or r >= len(rows):
                    continue
                rows[r][i][0] += int(n or 0)
                rows[r][i][1] += int(ms or 0)
    return rows
