# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import threading

from ..shared import mw
from ...fsrs_math import FSRS_CARD_COLS, FSRS_CARD_COND, add_memory_state, memory_state


# Results are memoized per (deck filter, scheduler day, cards-table fingerprint), so several FSRS
# widgets or deck switches skip the work. Any card change alters the fingerprint, so stale numbers
# are never served. The s/d values are extracted by SQLite (json_extract), so Python only receives
# numbers.
_FSRS_CACHE = {}
_FSRS_CACHE_LOCK = threading.Lock()
_FSRS_CACHE_MAX = 32

_S_EXPR = (
    "CASE WHEN json_valid(data) THEN coalesce("
    "json_extract(data, '$.s'), json_extract(data, '$.cd.s'), "
    "CASE WHEN json_valid(json_extract(data, '$.cd')) THEN json_extract(json_extract(data, '$.cd'), '$.s') END"
    ") END"
)
_DECAY_EXPR = "CASE WHEN json_valid(data) THEN json_extract(data, '$.decay') END"
_LRT_EXPR = "CASE WHEN json_valid(data) THEN json_extract(data, '$.lrt') END"
_D_EXPR = (
    "CASE WHEN json_valid(data) THEN coalesce("
    "json_extract(data, '$.d'), json_extract(data, '$.cd.d'), "
    "CASE WHEN json_valid(json_extract(data, '$.cd')) THEN json_extract(json_extract(data, '$.cd'), '$.d') END"
    ") END"
)


def _col_mod():
    # Fingerprint of the cards table. col.mod is not used because it also changes on
    # unrelated writes (like selecting a deck), which recomputed the FSRS stats on
    # every navigation. Any card change bumps its mod, so (count, max, total) of
    # cards.mod changes too.
    try:
        row = mw.col.db.first("SELECT count(), max(mod), total(mod) FROM cards")
        return (id(mw.col),) + tuple(row) if row else None
    except Exception:
        return None


def _empty():
    return {"stability": {}, "difficulty": {}, "retrievability": {}}


def _fetch_sql(did_limit, today_sched):
    """The memory states read by SQLite (json_extract); counted as in Anki's graphs."""
    import time

    now = int(time.time())
    res = _empty()
    rows = mw.col.db.all(
        f"""
        SELECT {_S_EXPR}, {_D_EXPR}, {_DECAY_EXPR}, {_LRT_EXPR},
               cards.due, cards.odue, cards.odid, cards.ivl, cards.queue, cards.type
        FROM cards AS cards
        WHERE {FSRS_CARD_COND}
        {did_limit}
        """
    )
    for s, d, decay, lrt, due, odue, odid, ivl, queue, ctype in rows:
        if s is None or d is None:
            continue  # no memory state (or binary data: the Python path reads it)
        try:
            mem = (float(s), float(d), decay, lrt)
        except (TypeError, ValueError):
            continue
        add_memory_state(res, mem, due, odue, odid, ivl, queue, ctype, today_sched, now)
    return res


def _fetch_python(did_limit, today_sched):
    """Legacy path (protobuf/bytes card data or a SQLite without JSON1)."""
    import time

    now = int(time.time())
    res = _empty()
    rows = mw.col.db.all(f"SELECT {FSRS_CARD_COLS} FROM cards AS cards WHERE {FSRS_CARD_COND} {did_limit}")
    for data, due, odue, odid, ivl, queue, ctype in rows:
        mem = memory_state(data)
        if mem is not None:
            add_memory_state(res, mem, due, odue, odid, ivl, queue, ctype, today_sched, now)
    return res


def _copy_result(res):
    return {k: dict(v) for k, v in res.items()}


def fetch_fsrs_stats(provider_cls, addon_config, deck_id=None, is_deleted=False, did_limit=None):
    if is_deleted:
        did_limit = "AND (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END) IS NULL"
    elif did_limit is None:
        did_limit = provider_cls._get_did_limit(addon_config, deck_id)

    today_sched = mw.col.sched.today
    key = (did_limit, today_sched, _col_mod())
    if key[2] is not None:
        with _FSRS_CACHE_LOCK:
            hit = _FSRS_CACHE.get(key)
        if hit is not None:
            return _copy_result(hit)

    try:
        res = _fetch_sql(did_limit, today_sched)
    except Exception:
        res = _fetch_python(did_limit, today_sched)

    if key[2] is not None:
        with _FSRS_CACHE_LOCK:
            if len(_FSRS_CACHE) >= _FSRS_CACHE_MAX:
                _FSRS_CACHE.clear()
            _FSRS_CACHE[key] = res
    return _copy_result(res)
