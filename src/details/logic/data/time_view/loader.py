# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""High-level orchestration functions for loading statistical data."""

from .....utils import excluded_days_clause
from aqt import mw
from ... import REVLOG_RESCHED, Period, excluded_decks_clause
from .....utils import get_logical_day_sql
from ..core.time_utils import get_time_range_ms
from ..core.database import fetch_data
from ..transforms import process_deck_tree, calculate_totals
from .static import (
    get_time_view_static_bundle,
)
from ...logger import log_swallowed


def _add_day_stats(totals, range_type, custom_days, custom_type, start_date_str, end_date_str):
    """Add the day-level figures the extra stat cards need (read from the cached daily history)."""
    from ...history_cache import GlobalHistoryCache
    from ....widgets.stats_cards.logic.model import deck_state_from_context, history_day_stats

    try:
        ctx = GlobalHistoryCache.get_context(
            None, range_type, custom_days=custom_days, custom_type=custom_type,
            start_date_str=start_date_str, end_date_str=end_date_str, allow_sync_check=False,
        )
        day_stats = history_day_stats((ctx or {}).get("reviews") or [])
    except Exception:
        return
    try:
        totals.update(deck_state_from_context(GlobalHistoryCache.get_context(None, Period.TOTAL, allow_sync_check=False)))
    except Exception:
        log_swallowed()
    if day_stats["days_in_period"]:
        totals["days_in_period"] = day_stats["days_in_period"]
        totals["period_active_days"] = day_stats["active_days"]
        totals["longest_streak"] = day_stats["longest_streak"]
        totals["best_day"] = day_stats["best_day"]


def load_stats_data(range_type, excluded_dids, spark_precision, show_trends,
                   week_start, custom_days=7, custom_type="relative",
                   start_date_str="", end_date_str=""):
    """
    Main orchestration function for loading all statistics data for Time View.
    Returns a dictionary containing results, totals, tree data, and metadata.
    """
    start_ms, end_ms, prev_start_ms, prev_end_ms = get_time_range_ms(
        range_type, week_start, custom_days, custom_type, start_date_str, end_date_str, show_trends
    )

    from ...logger import log_debug

    did_limit = excluded_decks_clause(excluded_dids)

    from ...history_cache import GlobalHistoryCache
    ghc = GlobalHistoryCache()
    if ghc.is_initialized:
        from ..transforms import adapter_from_cache
        log_debug(f"[LOADER] Attempting cache adapter for range={range_type}", tag="LOADER")
        cache_data = adapter_from_cache(
            ghc, range_type, spark_precision,
            start_ms=start_ms, end_ms=end_ms,
            excluded_dids=excluded_dids
        )
        if cache_data:
            results, prev_stats_map, activity_map, retention_maps, bin_labels, bin_count = cache_data
            static_bundle, _cache_hit = get_time_view_static_bundle(excluded_dids)

            if show_trends and range_type != Period.TOTAL:
                log_debug(f"[LOADER] Cache trend lookup: {prev_start_ms} to {prev_end_ms}", tag="LOADER")
                prev_cache = adapter_from_cache(
                    ghc, Period.CUSTOM, spark_precision,
                    start_ms=prev_start_ms, end_ms=prev_end_ms,
                    excluded_dids=excluded_dids
                )
                if prev_cache:
                    for pr in prev_cache[0]:
                        prev_stats_map[pr[0]] = pr

            deck_limits = static_bundle["deck_limits"]
            remaining_new_map = static_bundle["remaining_new_map"]
            streak_map = static_bundle["streak_map"]
            deck_name_maps = static_bundle["deck_name_maps"]

            flattened_results, tree_data = process_deck_tree(
                results, prev_stats_map, activity_map, retention_maps, deck_limits, remaining_new_map, bin_labels, bin_count, show_trends,
                streak_map=streak_map, deck_name_maps=deck_name_maps
            )

            totals = calculate_totals(
                results, prev_stats_map, deck_limits, remaining_new_map, bin_labels, retention_maps, bin_count
            )
            range_ctx = ghc.get_context(
                None, range_type,
                custom_days=custom_days, custom_type=custom_type,
                start_date_str=start_date_str, end_date_str=end_date_str,
                allow_sync_check=False,
            ) or {}
            totals["active_days"] = (range_ctx.get("stats") or {}).get("active_days", 0)
            g_current, g_longest = streak_map.get("collection", (0, 0))
            totals["streak_current"] = g_current
            totals["streak_longest"] = g_longest
            _add_day_stats(totals, range_type, custom_days, custom_type, start_date_str, end_date_str)

            return {
                "results": flattened_results, "totals": totals, "tree_data": tree_data,
                "range_info": {"start_ms": start_ms, "end_ms": end_ms},
                "meta": {"bin_labels": bin_labels, "bin_count": bin_count}
            }

    log_debug(f"[LOADER] SQL FALLBACK for range={range_type}", tag="LOADER")
    static_bundle, _cache_hit = get_time_view_static_bundle(excluded_dids)
    results, prev_stats_map, activity_map, retention_maps, deck_limits, remaining_new_map, bin_labels, bin_count, start_ms, end_ms = fetch_data(
        start_ms, end_ms, prev_start_ms, prev_end_ms, did_limit, range_type, spark_precision, show_trends, precomputed_static=static_bundle
    )

    streak_map = static_bundle["streak_map"]

    # Deck name maps are built here from mw.col, which is safe to read from background threads.
    flattened_results, tree_data = process_deck_tree(
        results, prev_stats_map, activity_map, retention_maps, deck_limits, remaining_new_map, bin_labels, bin_count, show_trends,
        streak_map=streak_map, deck_name_maps=static_bundle["deck_name_maps"]
    )

    totals = calculate_totals(
        results, prev_stats_map, deck_limits, remaining_new_map, bin_labels, retention_maps, bin_count
    )

    total_active_days_query = f"""
        SELECT COUNT(DISTINCT {get_logical_day_sql('(CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END)')})
        FROM revlog
        LEFT JOIN cards ON revlog.cid = cards.id
        WHERE revlog.type < {REVLOG_RESCHED}
        AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) >= {start_ms}
        AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) < {end_ms}
        {did_limit} {excluded_days_clause()}
    """
    total_active_days = mw.col.db.scalar(total_active_days_query) or 0
    totals["active_days"] = total_active_days

    g_current, g_longest = streak_map.get("collection", (0, 0))
    totals["streak_current"] = g_current
    totals["streak_longest"] = g_longest

    return {
        "results": flattened_results,
        "totals": totals,
        "tree_data": tree_data,
        "range_info": {
            "start_ms": start_ms,
            "end_ms": end_ms
        },
        "meta": {
            "bin_labels": bin_labels,
            "bin_count": bin_count
        }
    }








