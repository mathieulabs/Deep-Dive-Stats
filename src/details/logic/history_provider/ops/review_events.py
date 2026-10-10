# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Individual reviews inside a short time window (one row per revlog entry)."""
from .....utils import excluded_days_clause, excluded_days_need_cards
from ..shared import REVLOG_RESCHED, mw
from ...data.core.empty_deck import did_limit_has_no_cards

# Kinds: 0 learning, 1 young, 2 mature, 3 relearning, 4 filtered
KIND_LEARN, KIND_YOUNG, KIND_MATURE, KIND_RELEARN, KIND_CRAM = range(5)
MAX_EVENTS = 1200


def _kind(rev_type, last_ivl):
    if rev_type == 0:
        return KIND_LEARN
    if rev_type == 2:
        return KIND_RELEARN
    if rev_type == 3:
        return KIND_CRAM
    return KIND_MATURE if (last_ivl or 0) >= 21 else KIND_YOUNG


def fetch_review_events(provider_cls, addon_config, deck_id, is_deleted, start_ms, end_ms, limit=MAX_EVENTS):
    """Return [(ts_ms, time_ms, ease, kind, cid)] oldest first, or None if more than `limit` reviews."""
    if is_deleted:
        did_limit = "AND (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END) IS NULL"
    else:
        did_limit = provider_cls._get_did_limit(addon_config, deck_id)
    if did_limit_has_no_cards(did_limit):
        return []
    join_clause = "LEFT JOIN cards ON revlog.cid = cards.id" if (did_limit or excluded_days_need_cards()) else ""
    start_ms, end_ms, limit = int(start_ms), int(end_ms), int(limit)
    # Two id ranges keep the primary key index usable (old revlogs store seconds).
    rows = mw.col.db.all(
        f"""
        SELECT revlog.id, revlog.time, revlog.ease, revlog.type, revlog.lastIvl, revlog.cid
        FROM revlog
        {join_clause}
        WHERE revlog.type < {REVLOG_RESCHED}
        AND ((revlog.id >= {start_ms} AND revlog.id < {end_ms})
             OR (revlog.id >= {start_ms // 1000} AND revlog.id < {end_ms // 1000}))
        {did_limit} {excluded_days_clause()}
        ORDER BY revlog.id
        LIMIT {limit + 1}
        """
    )
    if len(rows) > limit:
        return None
    out = []
    for rid, t, ease, rtype, last_ivl, cid in rows:
        ts = rid if rid > 1000000000000 else rid * 1000
        out.append((int(ts), int(t or 0), int(ease or 0), _kind(rtype, last_ivl), int(cid)))
    return out
