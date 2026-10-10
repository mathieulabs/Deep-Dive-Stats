# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Card states and intervals for deleted cards.

A deleted card only survives through its review log, so its state is read from its
last review: the new interval says young, mature or still in learning. This is the
state the card had when it was last seen, not when it was deleted.
"""
from aqt import mw

_cache = {"key": None, "value": None}


def _classify(rev_type, ivl):
    if ivl >= 21:
        return "mature"
    if ivl > 0:
        return "young"
    return "relearn" if rev_type in (1, 2) else "learn"


def deleted_card_states():
    """Return {"counts": {...}, "intervals": {days: count}} for the deleted cards, cached per collection change."""
    try:
        key = (
            mw.col.db.scalar("select max(id) from revlog") or 0,
            mw.col.db.scalar("select count() from cards") or 0,
        )
    except Exception:
        return None
    if _cache["key"] == key:
        return _cache["value"]

    rows = mw.col.db.all(
        """
        SELECT r.type, r.ivl
        FROM revlog r
        JOIN (
            SELECT cid, MAX(id) AS mid
            FROM revlog
            WHERE cid NOT IN (SELECT id FROM cards)
            GROUP BY cid
        ) m ON r.id = m.mid
        """
    )
    counts = {"learn": 0, "relearn": 0, "young": 0, "mature": 0}
    intervals = {}
    for rev_type, ivl in rows:
        counts[_classify(rev_type, ivl)] += 1
        if ivl > 0:
            intervals[ivl] = intervals.get(ivl, 0) + 1
    value = {"counts": counts, "intervals": intervals}
    _cache["key"] = key
    _cache["value"] = value
    return value


def deleted_review_intervals():
    """Review-intervals payload built from each deleted card's last review."""
    info = deleted_card_states()
    if not info:
        return None
    dist = info["intervals"]
    values = sorted(dist)
    total = sum(dist.values())

    def pct(share):
        running = 0
        for v in values:
            running += dist[v]
            if running >= total * share:
                return v
        return 0

    p50 = pct(0.5) if total else 31
    p95 = pct(0.95) if total else 365
    return {
        "distribution": dict(dist), "total": total,
        "median": p50 if total else 0, "p50": p50, "p95": p95,
    }


def enrich_deleted_context(ctx):
    """Copy of a deleted-cards context with card states and review intervals filled in."""
    if not isinstance(ctx, dict) or ctx.get("_deleted_states"):
        return ctx
    try:
        info = deleted_card_states()
        intervals = deleted_review_intervals()
    except Exception:
        return ctx
    if not info:
        return ctx

    out = dict(ctx)
    counts = dict(ctx.get("counts") or {})
    counts.update(info["counts"])
    out["counts"] = counts
    out["review_intervals"] = intervals
    out["_deleted_states"] = True
    return out
