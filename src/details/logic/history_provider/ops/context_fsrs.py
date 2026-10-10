# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import threading

from ..shared import mw
from ...fsrs_math import retrievability
from ...logger import log_swallowed


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


def _accumulate(rows_sd, rows_rev, today_sched):
    stability_counts = {}
    difficulty_counts = {}
    retrievability_counts = {}

    for s, d in rows_sd:
        try:
            s = float(s) if s is not None else 0.0
        except (TypeError, ValueError):
            s = 0.0
        try:
            d = float(d) if d is not None else 0.0
        except (TypeError, ValueError):
            d = 0.0
        if s > 0:
            s_int = int(s)
            if s_int > 100:
                s_int = 100  # cap to avoid infinite charts
            stability_counts[s_int] = stability_counts.get(s_int, 0) + 1
        if d > 0:
            # difficulty is 1-10 -> percent
            diff_pct = int(((d - 1) / 9.0) * 100)
            diff_pct = max(0, min(100, diff_pct))
            difficulty_counts[diff_pct] = difficulty_counts.get(diff_pct, 0) + 1

    for due, ivl, s, decay in rows_rev:
        try:
            s = float(s) if s is not None else 0.0
        except (TypeError, ValueError):
            s = 0.0
        if s > 0:
            elapsed = max(0, today_sched - (due - ivl))
            r_pct = max(0, min(100, int(retrievability(elapsed, s, decay) * 100)))
            retrievability_counts[r_pct] = retrievability_counts.get(r_pct, 0) + 1

    return {
        "stability": stability_counts,
        "difficulty": difficulty_counts,
        "retrievability": retrievability_counts,
    }


def _fetch_sql(did_limit, today_sched):
    rows_sd = mw.col.db.all(
        f"""
        SELECT {_S_EXPR}, {_D_EXPR}
        FROM cards
        WHERE queue IN (1,2,3) AND ivl > 0
        {did_limit}
        """
    )
    rows_rev = mw.col.db.all(
        f"""
        SELECT cards.due, cards.ivl, {_S_EXPR}, {_DECAY_EXPR}
        FROM cards
        WHERE cards.queue = 2 AND cards.ivl > 0
        {did_limit}
        """
    )
    return _accumulate(rows_sd, rows_rev, today_sched)


def _fetch_python(did_limit, today_sched):
    """Legacy path (protobuf/bytes card data or a SQLite without JSON1)."""
    import json

    try:
        from anki.cards_pb2 import CardData
        has_pb = True
    except ImportError:
        CardData = None
        has_pb = False

    def _extract(data, want_d=True):
        s = 0.0
        d = 0.0
        decay = None
        if not data:
            return s, d, None
        if isinstance(data, bytes) and has_pb:
            try:
                cd = CardData.FromString(data)
                if cd.HasField("fsrs"):
                    s = cd.fsrs.stability
                    d = cd.fsrs.difficulty
            except Exception:
                log_swallowed()
        elif isinstance(data, str):
            try:
                jd = json.loads(data)
                if "s" in jd and (not want_d or "d" in jd):
                    s = float(jd["s"])
                    d = float(jd.get("d", 0.0))
                    decay = jd.get("decay")
                elif "cd" in jd:
                    cd = jd["cd"]
                    if isinstance(cd, str):
                        cd = json.loads(cd)
                    if "s" in cd and (not want_d or "d" in cd):
                        s = float(cd["s"])
                        d = float(cd.get("d", 0.0))
            except Exception:
                log_swallowed()
        return s, d, decay

    rows = mw.col.db.all(
        f"SELECT data FROM cards WHERE queue IN (1,2,3) AND ivl > 0 {did_limit}"
    )
    rows_sd = [_extract(r[0])[:2] for r in rows]
    rev = mw.col.db.all(
        f"SELECT cards.due, cards.ivl, cards.data FROM cards WHERE cards.queue = 2 AND cards.ivl > 0 {did_limit}"
    )
    rows_rev = [(due, ivl, *_extract(data, want_d=False)[::2]) for due, ivl, data in rev]
    return _accumulate(rows_sd, rows_rev, today_sched)


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
