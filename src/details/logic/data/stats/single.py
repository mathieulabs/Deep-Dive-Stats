# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Deck-specific stats loading routines for deck view."""

from .....utils import excluded_days_clause

from aqt import mw

from ... import LAST_YEAR, REVLOG_RESCHED, Period, get_rollover_offset_ms
from ..core.streaks import get_deck_streaks
from ..core.time_utils import get_time_range_ms
from .shared import build_collection_did_limit, resolve_prev_exact_bounds


def fetch_deck_stats(deck_id, tabs_config, excluded_dids, show_trends, week_start, spark_precision, is_collection=False, pin_top=True):
    """
    Fetches statistics for a single deck across multiple time ranges (tabs).
    Returns a list of dictionaries containing data for each range.
    """
    stats_data = []
    
    offset_ms = get_rollover_offset_ms()
    ms_per_day = 86400 * 1000
    
    child_ids = []
    if is_collection:
        did_filter = build_collection_did_limit(excluded_dids)
    elif deck_id is None:
        did_filter = "AND (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END) IS NULL"
    else:
        child_ids = mw.col.decks.deck_and_child_ids(deck_id)
        if len(child_ids) == 1:
            did_filter = f"AND (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END) = {deck_id}"
        else:
            did_filter = f"AND (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END) IN ({','.join(map(str, child_ids))})"

    limit = 0
    remaining_new = 0
    max_days = None
    if is_collection:
        try:
            deck_limits = {}
            for d in mw.col.decks.all_names_and_ids():
                if excluded_dids and d.id in excluded_dids:
                    continue
                try:
                    conf = mw.col.decks.config_dict_for_deck_id(d.id)
                    deck_limits[d.id] = conf['new']['perDay']
                except Exception:
                    deck_limits[d.id] = 20

            if deck_limits:
                dids_csv = ",".join(map(str, deck_limits.keys()))
                rem_rows = mw.col.db.all(
                    f"SELECT (CASE WHEN odid > 0 THEN odid ELSE did END), COUNT(*) FROM cards WHERE type = 0 AND (CASE WHEN odid > 0 THEN odid ELSE did END) IN ({dids_csv}) GROUP BY 1"
                )
                rem_map = dict(rem_rows)
            else:
                rem_map = {}

            limit = sum(deck_limits.values())
            remaining_new = sum(rem_map.values())

            # Forecast bottleneck for collection = slowest deck
            max_days = 0.0
            for did, lim in deck_limits.items():
                if lim > 0:
                    max_days = max(max_days, rem_map.get(did, 0) / lim)
        except Exception:
            limit = 0
            remaining_new = 0
            max_days = None
    elif deck_id is None:
        # Deleted pseudo-deck: no forecast semantics
        limit = 0
        remaining_new = 0
        max_days = None
    else:
        try:
            deck_limits = {}
            target_ids = child_ids if child_ids else [deck_id]
            for cid in target_ids:
                try:
                    conf = mw.col.decks.config_dict_for_deck_id(cid)
                    deck_limits[cid] = conf['new']['perDay']
                except Exception:
                    deck_limits[cid] = 20
            limit = sum(deck_limits.values())

            rem_query = f"SELECT (CASE WHEN odid > 0 THEN odid ELSE did END), COUNT(*) FROM cards WHERE type = 0 {did_filter} GROUP BY 1"
            rem_rows = mw.col.db.all(rem_query)
            rem_map = dict(rem_rows)
            remaining_new = sum(rem_map.values())

            # Forecast bottleneck for folder (and equivalent for leaf)
            max_days = 0.0
            for did, lim in deck_limits.items():
                if lim > 0:
                    max_days = max(max_days, rem_map.get(did, 0) / lim)
        except Exception:
            limit = 20
            remaining_new = 0
            max_days = None

    # Disable cache for folders (multi-DID) for now to make sure correct aggregation,
    # as the cache is indexed by individual leaf DIDs.
    _cacheable = {Period.TOTAL, Period.YEAR, Period.MONTH, Period.WEEK, Period.TWO_WEEKS, Period.TODAY, Period.YESTERDAY, LAST_YEAR}
    if deck_id is not None and not is_collection and not child_ids:
        from ...history_cache import GlobalHistoryCache
        from ...logger import log_debug
        ghc = GlobalHistoryCache()
        if ghc.is_initialized and deck_id in ghc.cache:
            c_s, l_s = get_deck_streaks(deck_id, start_ms=0, end_ms=None)
            for tab_config in tabs_config:
                range_type = tab_config.get("range", Period.WEEK)
                if range_type not in _cacheable:
                    continue  # Skip short ranges, SQL handles these
                ctx = ghc.get_context(deck_id, range_type, cfg=None,
                    custom_days=tab_config.get("days", 7),
                    custom_type=tab_config.get("custom_type", "relative"),
                    start_date_str=tab_config.get("start_date", ""),
                    end_date_str=tab_config.get("end_date", ""))
                if not ctx:
                    continue
                    
                s = ctx.get("stats", {})
                
                start_ms, end_ms, _tp_start, _tp_end = get_time_range_ms(
                    range_type,
                    week_start=tab_config.get("week_start", week_start), 
                    custom_days=tab_config.get("days", 7),
                    custom_type=tab_config.get("custom_type", "relative"),
                    start_date_str=tab_config.get("start_date", ""),
                    end_date_str=tab_config.get("end_date", ""),
                    show_trends=True,
                )
                
                # Mock 'res' tuple for components expecting the raw db row
                mock_res = (
                    0, s.get("total_time_ms", 0), s.get("total_reviews", 0),
                    s.get("total_passed", 0), s.get("pass_young", 0), s.get("rev_young", 0),
                    s.get("pass_mat", 0), s.get("rev_mat", 0),
                    s.get("again", 0), s.get("hard", 0), s.get("good", 0), s.get("easy", 0),
                    ""
                )

                prev_res = [0]*13
                if show_trends and range_type != Period.TOTAL:
                    p_start_ms, p_end_ms = _tp_start, _tp_end
                    
                    p_lb, p_ub = resolve_prev_exact_bounds(p_start_ms, p_end_ms)

                    prev_ctx = ghc.get_context(deck_id, Period.CUSTOM, cfg=None, 
                        custom_type="exact", start_date_str=p_lb, end_date_str=p_ub)
                        
                    if prev_ctx:
                        ps = prev_ctx.get("stats", {})
                        prev_res = (
                            0, ps.get("total_time_ms", 0), ps.get("total_reviews", 0),
                            ps.get("total_passed", 0), ps.get("pass_young", 0), ps.get("rev_young", 0),
                            ps.get("pass_mat", 0), ps.get("rev_mat", 0),
                            ps.get("again", 0), ps.get("hard", 0), ps.get("good", 0), ps.get("easy", 0),
                            ""
                        )

                stats_data.append({
                    "tab_config": tab_config,
                    "range_type": range_type,
                    "title": tab_config.get("title", "Stats"),
                    "start_ms": start_ms, "end_ms": end_ms,
                    "time_s": s.get("total_time_ms", 0) / 1000.0,
                    "reviews": s.get("total_reviews", 0),
                    "passed": s.get("total_passed", 0),
                    "pass_young": s.get("pass_young", 0), "rev_young": s.get("rev_young", 0),
                    "pass_mat": s.get("pass_mat", 0), "rev_mat": s.get("rev_mat", 0),
                    "active_days": s.get("active_days", 0),
                    "streak_current": c_s, "streak_longest": l_s,
                    "again": s.get("again", 0), "hard": s.get("hard", 0),
                    "good": s.get("good", 0), "easy": s.get("easy", 0),
                    "prev_reviews": 0, "prev_passed": 0, "prev_time_s": 0,
                    "fsrs": ctx.get("fsrs", {}),
                    "res": mock_res,
                    "prev_res": prev_res,
                    "limit": limit,
                    "remaining_new": remaining_new,
                    "max_days": max_days,
                    "is_from_cache": True
                })
            # Only skip SQL if ALL cacheable tabs got cache hits
            cacheable_tabs = [t for t in tabs_config if t.get("range") in _cacheable]
            log_debug(f"[LOADER] Cache results: {len(stats_data)} / {len(cacheable_tabs)} cacheable tabs hit", tag="LOADER")
            if stats_data and len(stats_data) == len(cacheable_tabs) and len(cacheable_tabs) == len(tabs_config):
                return stats_data
            # Mixed or partial, fall through to SQL for all tabs
            stats_data = []

    total_tab = None
    other_tabs = []
    for tab in tabs_config:
        if tab.get("range") == Period.TOTAL:
            total_tab = tab
        else:
            other_tabs.append(tab)
    
    if pin_top:
        ordered_tabs = ([total_tab] if total_tab else []) + other_tabs
    else:
        ordered_tabs = other_tabs + ([total_tab] if total_tab else [])
    
    # Pre-compute streaks ONCE for this deck (reused across all tabs)
    if is_collection:
        c_s, l_s = get_deck_streaks(None, start_ms=0, end_ms=None, excluded_dids=excluded_dids)
    elif deck_id is not None:
        c_s, l_s = get_deck_streaks(deck_id, start_ms=0, end_ms=None)
    else:
        c_s, l_s = 0, 0
    
    for tab_config in ordered_tabs:
        title = tab_config.get("title", "Stats")
        range_type = tab_config.get("range", Period.WEEK)
        week_start = tab_config.get("week_start", week_start)
        
        start_ms, end_ms, _tp_start, _tp_end = get_time_range_ms(
            range_type, 
            week_start=tab_config.get("week_start", week_start),
            custom_days=tab_config.get("days", 7),
            custom_type=tab_config.get("custom_type", "relative"),
            start_date_str=tab_config.get("start_date", ""),
            end_date_str=tab_config.get("end_date", ""),
            show_trends=True,
        )
        
        query = f"""
            SELECT 
                SUM(CASE WHEN revlog.time > 0 THEN revlog.time ELSE 0 END) as total_time,
                COUNT(revlog.id) as reviews,
                SUM(CASE WHEN revlog.ease > 1 THEN 1 ELSE 0 END) as passed,
                SUM(CASE WHEN revlog.lastIvl >= 1 AND revlog.lastIvl < 21 AND revlog.ease > 1 THEN 1 ELSE 0 END) as pass_young,
                SUM(CASE WHEN revlog.lastIvl >= 1 AND revlog.lastIvl < 21 THEN 1 ELSE 0 END) as rev_young,
                SUM(CASE WHEN revlog.lastIvl >= 21 AND revlog.ease > 1 THEN 1 ELSE 0 END) as pass_mat,
                SUM(CASE WHEN revlog.lastIvl >= 21 THEN 1 ELSE 0 END) as rev_mat,
                SUM(CASE WHEN revlog.ease = 1 THEN 1 ELSE 0 END) as count_again,
                SUM(CASE WHEN revlog.ease = 2 THEN 1 ELSE 0 END) as count_hard,
                SUM(CASE WHEN revlog.ease = 3 THEN 1 ELSE 0 END) as count_good,
                SUM(CASE WHEN revlog.ease = 4 THEN 1 ELSE 0 END) as count_easy,
                COUNT(DISTINCT CAST(((CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END - {offset_ms}) / {ms_per_day}) AS INT)) as active_days
            FROM revlog
            LEFT JOIN cards ON revlog.cid = cards.id
            WHERE revlog.type < {REVLOG_RESCHED}
            AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) >= {start_ms}
            AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) < {end_ms}
            {did_filter} {excluded_days_clause()}
        """
        
        res = mw.col.db.first(query)
        if res:
            res = (deck_id or 0,) + tuple(res)
        else:
            res = [deck_id or 0] + [0] * 12

        prev_res = [deck_id or 0] + [0] * 12
        if show_trends and range_type != Period.TOTAL:
            p_start_ms, p_end_ms = _tp_start, _tp_end
            from ...history_cache import GlobalHistoryCache
            
            ghc = GlobalHistoryCache()
            p_lb, p_ub = resolve_prev_exact_bounds(p_start_ms, p_end_ms)
            

            lookup_id = deck_id if not is_collection else None
            prev_ctx = ghc.get_context(lookup_id, Period.CUSTOM, cfg=None, 
                                       custom_type="exact", start_date_str=p_lb, end_date_str=p_ub)
            
            if prev_ctx:
                ps = prev_ctx.get("stats", {})
                prev_res = (
                    deck_id or 0, ps.get("total_time_ms", 0), ps.get("total_reviews", 0),
                    ps.get("total_passed", 0), ps.get("pass_young", 0), ps.get("rev_young", 0),
                    ps.get("pass_mat", 0), ps.get("rev_mat", 0),
                    ps.get("again", 0), ps.get("hard", 0), ps.get("good", 0), ps.get("easy", 0),
                    ""
                )
            else:
                prev_query = f"""
                    SELECT 
                        SUM(CASE WHEN revlog.time > 0 THEN revlog.time ELSE 0 END) as total_time,
                        COUNT(revlog.id) as reviews,
                        SUM(CASE WHEN revlog.ease > 1 THEN 1 ELSE 0 END) as passed,
                        SUM(CASE WHEN revlog.lastIvl >= 1 AND revlog.lastIvl < 21 AND revlog.ease > 1 THEN 1 ELSE 0 END) as pass_young,
                        SUM(CASE WHEN revlog.lastIvl >= 1 AND revlog.lastIvl < 21 THEN 1 ELSE 0 END) as rev_young,
                        SUM(CASE WHEN revlog.lastIvl >= 21 AND revlog.ease > 1 THEN 1 ELSE 0 END) as pass_mat,
                        SUM(CASE WHEN revlog.lastIvl >= 21 THEN 1 ELSE 0 END) as rev_mat,
                        SUM(CASE WHEN revlog.ease = 1 THEN 1 ELSE 0 END) as count_again,
                        SUM(CASE WHEN revlog.ease = 2 THEN 1 ELSE 0 END) as count_hard,
                        SUM(CASE WHEN revlog.ease = 3 THEN 1 ELSE 0 END) as count_good,
                        SUM(CASE WHEN revlog.ease = 4 THEN 1 ELSE 0 END) as count_easy,
                        COUNT(DISTINCT CAST(((CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END - {offset_ms}) / {ms_per_day}) AS INT)) as active_days
                    FROM revlog
                    LEFT JOIN cards ON revlog.cid = cards.id
                    WHERE revlog.type < {REVLOG_RESCHED}
                    AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) >= {p_start_ms}
                    AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) < {p_end_ms}
                    {did_filter} {excluded_days_clause()}
                """
                p_res = mw.col.db.first(prev_query)
                if p_res:
                    prev_res = (deck_id or 0,) + tuple(p_res)
                else:
                    prev_res = [deck_id or 0] + [0] * 12
        stats_data.append({
            "tab_config": tab_config,
            "range_type": range_type,
            "title": title,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "res": res,
            "prev_res": prev_res,
            "limit": limit,
            "remaining_new": remaining_new,
            "max_days": max_days,
            "active_days": res[12] if res and len(res) > 12 else 0,
            "streak_current": c_s,
            "streak_longest": l_s,
        })

    return stats_data






