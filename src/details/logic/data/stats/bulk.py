# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Bulk deck-range aggregation for deck view tabs."""

from aqt import mw

from ... import LAST_YEAR, Period
from ..core.database import fetch_data
from ..core.streaks import get_all_deck_streaks
from .shared import build_global_did_limit, resolve_prev_exact_bounds, resolve_tab_range


def fetch_all_decks_stats(deck_ids, tabs_config, excluded_dids, show_trends, week_start, spark_precision, pin_top=True):
    """
    Fetches statistics for ALL decks across ALL time ranges in bulk.
    Returns a dictionary mapping deck_id -> list of range stats.
    """
    did_limit = build_global_did_limit(excluded_dids)
    
    # Group ranges by type to avoid duplicate SQL queries if multiple tabs use same range
    range_types = {}
    for tab in tabs_config:
        r = tab.get("range", Period.WEEK)
        if r not in range_types:
            range_types[r] = tab
            
    # bulk_results: {range_type: {did: stats_tuple}}
    bulk_results = {}
    bulk_activity = {}
    bulk_retention = {}
    range_meta = {}
    
    for r_type, t_conf in range_types.items():
        start_ms, end_ms, p_start_ms, p_end_ms = resolve_tab_range(
            t_conf,
            default_week_start=week_start,
            show_trends=show_trends,
        )
        
        from ...history_cache import GlobalHistoryCache
        ghc = GlobalHistoryCache()
        
        # Sync once here and disable it in the loop below
        ghc._check_incremental_update()
        
        # Pre-fetch deck names so get_context does no SQL in the loop
        deck_names = {d.id: d.name for d in mw.col.decks.all_names_and_ids()}
        if not hasattr(tabs_config, "_deck_names"):
            # Minimal cfg stand-in that carries the pre-fetched names to get_context.
            class MockCfg:
                def __init__(self, names): self._deck_names = names
                @property
                def config(self): return {}
            names_cfg = MockCfg(deck_names)
        else:
            names_cfg = None

        _cacheable = {Period.TOTAL, Period.YEAR, Period.MONTH, LAST_YEAR}
        

        if r_type in _cacheable and ghc.is_initialized:
            res_map = {}
            prev_map = {}
            act_map = {}
            ret_maps = {"all": {}, "young": {}, "mature": {}}
            
            b_count = 365 if r_type in [Period.TOTAL, Period.YEAR, LAST_YEAR] else 30
            if not spark_precision:
                b_count = 365 if r_type == Period.TOTAL else (12 if r_type in [Period.YEAR, LAST_YEAR] else 30)

            for cid, c_data in ghc.cache.items():
                ctx = ghc.get_context(
                    cid, r_type, cfg=names_cfg,
                    custom_days=t_conf.get("days", 7),
                    custom_type=t_conf.get("custom_type", "relative"),
                    start_date_str=t_conf.get("start_date", ""),
                    end_date_str=t_conf.get("end_date", ""),
                    allow_sync_check=False # Already checked above
                )
                if not ctx: continue
                # Skip non-integer IDs (folders/totals) to prevent double/triple counting.
                # Numeric keys in the cache are "raw" non-aggregated stats.
                if not isinstance(cid, int): continue
                
                s = ctx.get("stats", {})
                cid_key = None if cid == -1 else cid
                
                res_map[cid_key] = (
                    cid_key, s.get("total_time_ms", 0), s.get("total_reviews", 0),
                    s.get("total_passed", 0), s.get("pass_young", 0), s.get("rev_young", 0),
                    s.get("pass_mat", 0), s.get("rev_mat", 0),
                    s.get("again", 0), s.get("hard", 0), s.get("good", 0), s.get("easy", 0),
                    ",".join(
                        str(day) for day, v in (ctx.get("heatmap_data") or {}).items()
                        if v.get("reviews", 0) > 0
                    )
                )
                
                if show_trends and r_type != Period.TOTAL:
                    p_lb, p_ub = resolve_prev_exact_bounds(p_start_ms, p_end_ms)

                    prev_ctx = ghc.get_context(cid, Period.CUSTOM, cfg=names_cfg, 
                        custom_type="exact", start_date_str=p_lb, end_date_str=p_ub,
                        allow_sync_check=False)
                        
                    if prev_ctx:
                        ps = prev_ctx.get("stats", {})
                        prev_map[cid_key] = (
                            cid_key, ps.get("total_time_ms", 0), ps.get("total_reviews", 0),
                            ps.get("total_passed", 0), ps.get("pass_young", 0), ps.get("rev_young", 0),
                            ps.get("pass_mat", 0), ps.get("rev_mat", 0),
                            ps.get("again", 0), ps.get("hard", 0), ps.get("good", 0), ps.get("easy", 0),
                            ""
                        )
                
                history_asc = ctx["reviews"][::-1]
                act_map[cid_key] = [h.get("reviews", 0) for h in history_asc]
                
                # Use the actual returned slice length to avoid IndexErrors in the aggregator
                b_count = max(b_count, len(history_asc))

                # Store as [ percentage, 100 ] so that p/t*100 = percentage in the sparkline calc
                ret_maps["all"][cid_key] = [[h.get("retention") or 0, 100] for h in history_asc]
                ret_maps["young"][cid_key] = [[h.get("ret_young") or 0, 100] for h in history_asc]
                ret_maps["mature"][cid_key] = [[h.get("ret_mat") or 0, 100] for h in history_asc]
                
            labels = []
        else:
            res, prev_map, act_map, ret_maps, _, _, labels, b_count, _, _ = fetch_data(
                start_ms, end_ms, p_start_ms, p_end_ms, did_limit, r_type, spark_precision, show_trends
            )
            # res is a list of tuples: (did, time, reviews, passed, ...)
            res_map = {row[0]: row for row in res}
            
        bulk_results[r_type] = (res_map, prev_map)
        bulk_activity[r_type] = act_map
        bulk_retention[r_type] = ret_maps
        range_meta[r_type] = {
            "start_ms": start_ms, "end_ms": end_ms,
            "labels": labels, "bin_count": b_count
        }

    streak_map = get_all_deck_streaks(did_limit)
    
    # Total limits and remaining new cards (collection-wide, grouped by did)
    # Single call, reused for both deck_limits and hierarchy building below.
    _all_decks = list(mw.col.decks.all_names_and_ids())
    deck_limits = {}
    for d in _all_decks:
        try:
            conf = mw.col.decks.config_dict_for_deck_id(d.id)
            deck_limits[d.id] = conf['new']['perDay']
        except Exception: deck_limits[d.id] = 20

    new_cards_results = mw.col.db.all(f"SELECT (CASE WHEN odid > 0 THEN odid ELSE did END), COUNT(*) FROM cards WHERE type = 0 {did_limit} GROUP BY 1")
    remaining_new_map = dict(new_cards_results)

    # Hierarchical aggregation in one O(N) pass, using a parent map built from deck names ("Parent::Child").
    _name_to_id = {d.name: d.id for d in _all_decks}
    _children_map = {d.id: [] for d in _all_decks}
    for d in _all_decks:
        if '::' in d.name:
            parent_name = d.name.rsplit('::', 1)[0]
            parent_id = _name_to_id.get(parent_name)
            if parent_id is not None:
                _children_map[parent_id].append(d.id)

    def _get_subtree(root_id):
        result = []
        stack = [root_id]
        while stack:
            cur = stack.pop()
            result.append(cur)
            stack.extend(_children_map.get(cur, []))
        return result

    _excluded = set(excluded_dids or [])
    hierarchical_limits = {}
    hierarchical_remaining = {}
    hierarchical_max_days = {}
    for d in _all_decks:
        d_id = d.id
        subtree = _get_subtree(d_id)
        h_lim = 0
        h_rem = 0
        m_days = 0.0
        for cid in subtree:
            if cid in _excluded:
                continue
            lim = deck_limits.get(cid, 0)
            rem = remaining_new_map.get(cid, 0)
            h_lim += lim
            h_rem += rem
            if lim > 0:
                m_days = max(m_days, rem / lim)
        hierarchical_limits[d_id] = h_lim
        hierarchical_remaining[d_id] = h_rem
        hierarchical_max_days[d_id] = m_days

    col_total_limit = sum(deck_limits.get(did, 0) for did in deck_limits if did not in (excluded_dids or []))
    col_total_remaining = sum(remaining_new_map.values())
    col_total_max_days = 0
    for did in remaining_new_map:
        if did in (excluded_dids or []): continue
        lim = deck_limits.get(did, 0)
        if lim > 0:
            col_total_max_days = max(col_total_max_days, remaining_new_map[did] / lim)

    # Assemble final structure: {deck_id: [range_1_data, range_2_data, ...]}
    final_data = {}
    
    # Only process decks in deck_ids (already filtered to those with data in deck_view.py).
    all_target_dids = list(deck_ids)
    
    for d_id in all_target_dids:
        deck_stats = []
        is_col = (d_id == "collection")
        actual_id = None if is_col else d_id
        
        for tab_config in tabs_config:
            r_type = tab_config.get("range", Period.WEEK)
            if r_type not in bulk_results: continue
            
            res_map, prev_map = bulk_results[r_type]
            act_map = bulk_activity[r_type]
            ret_maps = bulk_retention[r_type]
            meta = range_meta[r_type]
            
            # The collection row sums all decks (grouped queries are keyed by did).
            if is_col:
                sum_res = [0] * 12
                for did in res_map:
                    row = res_map[did]
                    for i in range(1, 12):
                        if i < len(row): sum_res[i] += (row[i] or 0)
                res_row = [None] + sum_res[1:]
                
                sum_prev = [0] * 12
                for did in prev_map:
                    row = prev_map[did]
                    for i in range(1, 12):
                        if i < len(row): sum_prev[i] += (row[i] or 0)
                prev_row = [None] + sum_prev[1:]
                
                all_active_days = set()
                for did in res_map:
                    row = res_map[did]
                    if len(row) > 12 and row[12]:
                        all_active_days.update(row[12].split(','))
                active_days_count = len(all_active_days)
                
                activity_list = [0] * meta["bin_count"]
                for did in act_map:
                    row_act = act_map[did]
                    for i in range(min(meta["bin_count"], len(row_act))): 
                        activity_list[i] += row_act[i]
                        
                ret_sparks = {}
                for k in ["all", "young", "mature"]:
                    sum_ret = [[0, 0] for _ in range(meta["bin_count"])]
                    for did in ret_maps[k]:
                        row_ret = ret_maps[k][did]
                        for i in range(min(meta["bin_count"], len(row_ret))):
                            sum_ret[i][0] += row_ret[i][0]
                            sum_ret[i][1] += row_ret[i][1]
                    ret_sparks[k] = [(p/t*100 if t>0 else 0) for p, t in sum_ret]
            else:
                res_row = res_map.get(actual_id)
                prev_row = prev_map.get(actual_id)
                
                if res_row is None: res_row = [actual_id] + [0] * 12
                if prev_row is None: prev_row = [actual_id] + [0] * 12
                
                raw_days = res_row[12] if len(res_row) > 12 and res_row[12] else ""
                active_days_count = len(set(raw_days.split(','))) if raw_days else 0
                
                activity_list = act_map.get(actual_id, [0] * meta["bin_count"])
                
                ret_sparks = {}
                for k in ["all", "young", "mature"]:
                    raw_sparks = ret_maps[k].get(actual_id, [[0, 0] for _ in range(meta["bin_count"])])
                    ret_sparks[k] = [(p/t*100 if t>0 else 0) for p, t in raw_sparks]

            c_s, l_s = streak_map.get(d_id, (0, 0))
            
            deck_stats.append({
                "tab_config": tab_config,
                "range_type": r_type,
                "title": tab_config.get("title", "Stats"),
                "start_ms": meta["start_ms"], "end_ms": meta["end_ms"],
                "res": res_row,
                "prev_res": prev_row,
                "limit": hierarchical_limits.get(actual_id, 20) if not is_col else col_total_limit,
                "remaining_new": hierarchical_remaining.get(actual_id, 0) if not is_col else col_total_remaining,
                "max_days": hierarchical_max_days.get(actual_id, 0) if not is_col else col_total_max_days,
                "activity": activity_list,
                "retention_sparks": ret_sparks,
                "active_days": active_days_count,
                "streak_current": c_s,
                "streak_longest": l_s
            })
            
        final_data[d_id] = deck_stats
        
    return final_data




