# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Database query functions for statistics fetching."""

from .....utils import excluded_days_clause
from aqt import mw
from ... import REVLOG_RESCHED, get_rollover_offset_ms


def fetch_data(start_ms, end_ms, prev_start_ms, prev_end_ms, did_limit, range_type, spark_precision, show_trends, precomputed_static=None):
    """
    Fetches the main statistics and previous statistics (if trends enabled).
    """
    from ...logger import log_debug
    
    offset_ms = get_rollover_offset_ms()
    ms_per_day = 86400 * 1000

    # Increase GROUP_CONCAT limit to avoid truncation for very large collections/long history
    mw.col.db.execute("PRAGMA group_concat_max_len = 100000")
    
    query = f"""
        SELECT (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END), 
               SUM(CASE WHEN revlog.time > 0 THEN revlog.time ELSE 0 END), 
               COUNT(revlog.id), 
               SUM(CASE WHEN revlog.ease > 1 THEN 1 ELSE 0 END),
               SUM(CASE WHEN revlog.lastIvl >= 1 AND revlog.lastIvl < 21 AND revlog.ease > 1 THEN 1 ELSE 0 END),
               SUM(CASE WHEN revlog.lastIvl >= 1 AND revlog.lastIvl < 21 THEN 1 ELSE 0 END),
               SUM(CASE WHEN revlog.lastIvl >= 21 AND revlog.ease > 1 THEN 1 ELSE 0 END),
               SUM(CASE WHEN revlog.lastIvl >= 21 THEN 1 ELSE 0 END),
               SUM(CASE WHEN revlog.ease = 1 THEN 1 ELSE 0 END), -- Again
               SUM(CASE WHEN revlog.ease = 2 THEN 1 ELSE 0 END), -- Hard
               SUM(CASE WHEN revlog.ease = 3 THEN 1 ELSE 0 END), -- Good
               SUM(CASE WHEN revlog.ease = 4 THEN 1 ELSE 0 END), -- Easy
               GROUP_CONCAT(DISTINCT CAST(((CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END - {offset_ms}) / {ms_per_day}) AS INT)) -- List of Active Day indices
        FROM revlog
        LEFT JOIN cards ON revlog.cid = cards.id
        WHERE revlog.type < {REVLOG_RESCHED}
        AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) >= {start_ms}
        AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) < {end_ms}
        {did_limit} {excluded_days_clause()}
        GROUP BY (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END)
        ORDER BY 2 DESC
    """
    results = mw.col.db.all(query)
    log_debug(f"[DATABASE] Main query returned {len(results)} rows", tag="DATABASE")
    
    prev_stats_map = {}
    if show_trends:
        case_stmt = "(CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END)"
        prev_query = query.replace(f"{case_stmt} >= {start_ms}", f"{case_stmt} >= {prev_start_ms}")\
                          .replace(f"{case_stmt} < {end_ms}", f"{case_stmt} < {prev_end_ms}")
        prev_results = mw.col.db.all(prev_query)
        for pr in prev_results:
            prev_stats_map[pr[0]] = pr

    if precomputed_static:
        deck_limits = dict(precomputed_static.get("deck_limits", {}) or {})
        remaining_new_map = dict(precomputed_static.get("remaining_new_map", {}) or {})
    else:
        deck_limits = {}
        for d in mw.col.decks.all_names_and_ids():
            try:
                conf = mw.col.decks.config_dict_for_deck_id(d.id)
                deck_limits[d.id] = conf['new']['perDay']
            except Exception:
                deck_limits[d.id] = 20

        new_cards_query = f"""
            SELECT (CASE WHEN odid > 0 THEN odid ELSE did END), COUNT(*) FROM cards WHERE type = 0 {did_limit} GROUP BY 1
        """
        new_cards_results = mw.col.db.all(new_cards_query)
        remaining_new_map = dict(new_cards_results)

    activity_map = {}
    retention_maps = {"all": {}, "young": {}, "mature": {}}
    bin_labels = []
    bin_count = 0

    return results, prev_stats_map, activity_map, retention_maps, deck_limits, remaining_new_map, bin_labels, bin_count, start_ms, end_ms


def fetch_dids_with_data():
    """Fetch all deck IDs that have at least one review."""
    # Walk the small cards table and probe revlog through its cid index instead of
    # scanning and joining the whole revlog (about 40x faster on 160k reviews).
    query = """
        SELECT DISTINCT (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END)
        FROM cards
        WHERE EXISTS (
            SELECT 1 FROM revlog
            WHERE revlog.cid = cards.id AND revlog.type < ?
        )
    """
    return [row[0] for row in mw.col.db.all(query, REVLOG_RESCHED)]



