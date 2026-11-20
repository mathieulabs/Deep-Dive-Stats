# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Rating by Sibling Gap: each review answer
of a mature card with the days since another card of the same note (a sibling) was last
answered, that sibling mature then too. Young cards are left out, as there: their ratings follow
their short intervals (Rating by Interval) more than their siblings.

The review history of the whole collection is read once, in order (one pass, each answer
with its note), then kept as four flat arrays (id, card, gap, rating) of the review answers
that had a sibling answered before: after new reviews only the new answers are added (the
last answer of each card of each note is kept for that). A review undone or removed: all
read again. A deck is a filter on the cards, a period a slice of the ids."""

import threading
from array import array
from bisect import bisect_left

from aqt import mw

_LOCK = threading.Lock()
# {"col", "phase", "base", "max_id", "count", "ids", "cids", "gaps", "eases",
#  "last": {nid: {cid: (day, mature after that answer)}}}
_STATE = {}

MAX_GAP = 30  # a sibling answered 30 days ago or more in the last bar
MATURE = 21  # days of interval, as everywhere else

_QUERY = """
    SELECT r.id, r.cid, c.nid, r.ease, r.type, r.ivl, r.lastIvl
    FROM revlog AS r JOIN cards AS c ON c.id = r.cid
    WHERE r.type < 4 AND r.ease BETWEEN 1 AND 4 {where}
    ORDER BY r.id
"""


def _feed(st, rows):
    """Adds the answers in order: a review answer (type 1) of a mature card (its interval before
    the answer) whose note's last answered other card was mature after that answer is kept with
    the days since; every answer is then the last one of its card."""
    base, last = st["base"], st["last"]
    ids, cids, gaps, eases = st["ids"], st["cids"], st["gaps"], st["eases"]
    for rid, cid, nid, ease, rtype, ivl, last_ivl in rows:
        day = (int(rid) // 1000 - base) // 86400
        seen = last.get(nid)
        if seen is None:
            seen = last[nid] = {}
        elif rtype == 1 and (last_ivl or 0) >= MATURE:
            prev = prev_mature = None
            for other, (d, mature) in seen.items():
                if other != cid and (prev is None or d > prev):
                    prev, prev_mature = d, mature
            if prev is not None and prev_mature:
                ids.append(int(rid))
                cids.append(int(cid))
                gaps.append(min(MAX_GAP, max(0, day - prev)))
                eases.append(int(ease))
        seen[cid] = (day, (ivl or 0) >= MATURE)


def _state():
    with _LOCK:  # one reader of the history at a time (the arrays are added to in place)
        from .revlog_stamp import revlog_stamp
        max_id, count = revlog_stamp()  # (kept: one read of the history for all the charts)
        max_id, count = int(max_id or 0), int(count or 0)
        cutoff = int(mw.col.sched.day_cutoff)
        phase = cutoff % 86400  # the hour the day starts at: another one moves every day
        st = _STATE
        same = st.get("col") == id(mw.col) and st.get("phase") == phase
        if same and st.get("max_id") == max_id and st.get("count") == count:
            return st
        if same and st.get("max_id") and count >= st.get("count", 0):
            new_rows = mw.col.db.scalar("SELECT count() FROM revlog WHERE id > ?", st["max_id"])
            if int(new_rows or 0) == count - st["count"]:
                # Only new reviews: added after the ones kept (a chart reading the arrays meanwhile
                # stays inside the ids it found).
                _feed(st, mw.col.db.all(_QUERY.format(where=f"AND r.id > {int(st['max_id'])}")))
                st["max_id"], st["count"] = max_id, count
                return st
        fresh = {"col": id(mw.col), "phase": phase, "base": cutoff - 86400 * 40000, "max_id": max_id, "count": count,
                 "ids": array("q"), "cids": array("q"), "gaps": array("b"), "eases": array("b"), "last": {}}
        _feed(fresh, mw.col.db.all(_QUERY.format(where="")))
        _STATE.clear()
        _STATE.update(fresh)
        return _STATE


def sibling_counts(limit, start_ms, end_ms):
    """{(days since a sibling's last answer, 0 the same day .. MAX_GAP, rating 1-4): reviews} of
    the review answers of the period (the cards of the decks: limit, review_buckets.did_limit)."""
    from .review_buckets import _memo

    def compute():
        st = _state()
        keep = None
        if (limit or "").strip():
            keep = {int(c) for c in mw.col.db.list(f"SELECT cards.id FROM cards WHERE 1 = 1 {limit}")}
        ids, cids, gaps, eases = st["ids"], st["cids"], st["gaps"], st["eases"]
        out = {}
        for i in range(bisect_left(ids, int(start_ms)), bisect_left(ids, int(end_ms))):
            if keep is not None and cids[i] not in keep:
                continue
            key = (gaps[i], eases[i])
            out[key] = out.get(key, 0) + 1
        return out

    return _memo(("siblings", limit, int(start_ms), int(end_ms), int(mw.col.sched.day_cutoff) % 86400), compute)
