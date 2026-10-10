# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Cache-adapter helpers for time-view transforms."""
from datetime import datetime
from functools import lru_cache


@lru_cache(maxsize=4096)
def _day_start_ms(day):
    return int(datetime.strptime(day, "%Y-%m-%d").timestamp() * 1000)


def adapter_from_cache(ghc, range_type, spark_precision, start_ms=None, end_ms=None, excluded_dids=None):
    """
    Transforms GlobalHistoryCache data into the legacy fetch_data format 
    expected by the Details window tree processor.
    Slices raw history to support any arbitrary time range.
    """
    from ... import Period, rollover_hour, get_rollover_offset_ms
    
    # Bins and labels for sparklines, using the same logic as database.py.
    if start_ms is None or end_ms is None:
        from ..core.time_utils import get_time_range_ms
        start_ms, end_ms, _, _ = get_time_range_ms(range_type, week_start=0)

    duration_ms = end_ms - start_ms
    if duration_ms <= 0: duration_ms = 86400000 

    bin_count = 30
    if range_type in [Period.TODAY, Period.YESTERDAY]:
        bin_count = 288 if spark_precision else 144
    elif range_type == Period.WEEK:
        bin_count = 168 if spark_precision else 7
    elif range_type == Period.TWO_WEEKS:
        bin_count = 336 if spark_precision else 14
    elif range_type == Period.MONTH:
        bin_count = 720 if spark_precision else 30
    elif range_type in [Period.YEAR, Period.TOTAL]:
        bin_count = 365
    
    bin_size_ms = duration_ms / bin_count
    
    from datetime import datetime
    months_en = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    bin_labels = []
    for i in range(bin_count):
        bin_start = start_ms + (i * bin_size_ms)
        dt = datetime.fromtimestamp(bin_start / 1000)
        if range_type in [Period.TODAY, Period.YESTERDAY]:
             lbl = dt.strftime("%H:%M")
        else:
             lbl = f"{months_en[dt.month-1]} {dt.day:02d}, {dt.year}"
        bin_labels.append(lbl)
    
    results = [] # [(did, time, rev, pass, p_young, r_young, p_mat, r_mat, again, hard, good, easy, active_days_str)]
    prev_stats_map = {}
    activity_map = {} # {did: [bin_counts]}
    retention_maps = {
        "all": {}, "young": {}, "mature": {}
    }
    
    from .....utils import split_excluded
    _ex_ids, _ex_deleted = split_excluded(excluded_dids)
    excluded_set = set(_ex_ids)
    offset_ms = get_rollover_offset_ms()
    ms_per_day = 86400 * 1000

    from datetime import timedelta
    off_h = rollover_hour()
    lb_date = (datetime.fromtimestamp(start_ms / 1000) - timedelta(hours=off_h)).strftime("%Y-%m-%d")
    ub_date = (datetime.fromtimestamp((end_ms - 1) / 1000) - timedelta(hours=off_h)).strftime("%Y-%m-%d")
    
    # Period.TOTAL from the cache is the source of truth for raw history
    for did in list(ghc.cache.keys()):
        ranges = ghc.cache[did]
        # Only raw decks (ints) and deleted cards (-1): string keys (folders) and None (collection) would be double counted, process_deck_tree aggregates by itself.
        if not isinstance(did, int): continue
        if did == -1 and _ex_deleted: continue
        if did != -1 and did in excluded_set: continue
        
        ctx_total = ranges.get(Period.TOTAL)
        if not ctx_total: continue
        
        history = ctx_total.get("reviews", []) # DESC order [ {logical_date, reviews, passed, ...} ]
        if not history: continue

        s_time = 0; s_rev = 0; s_pass = 0; s_p_young = 0; s_r_young = 0; s_p_mat = 0; s_r_mat = 0;
        s_again = 0; s_hard = 0; s_good = 0; s_easy = 0;
        active_day_indices = []
        
        # Entries carry a logical_date: convert it to a timestamp for the range check.
        for item in history:
            logical = item.get("logical_date", item.get("date", ""))
            if not logical: continue
            
            # Compare date strings first (much cheaper than strptime) and only parse dates inside the bounds.
            if lb_date <= logical <= ub_date:
                try:
                    # item_ms must add the offset_hour back to reach the exact Anki logical day start
                    item_ms = _day_start_ms(item["logical_date"]) + (off_h * 3600000)
                    
                    if start_ms <= item_ms < end_ms:
                        s_time += item.get("time_ms", 0)
                        s_rev += item.get("reviews", 0)
                        s_pass += item.get("passed", 0)
                        s_p_young += item.get("pass_young", 0)
                        s_r_young += item.get("rev_young", 0)
                        s_p_mat += item.get("pass_mat", 0)
                        s_r_mat += item.get("rev_mat", 0)
                        s_again += item.get("again", 0)
                        s_hard += item.get("hard", 0)
                        s_good += item.get("good", 0)
                        s_easy += item.get("easy", 0)
                        
                        day_idx = int((item_ms - offset_ms) / ms_per_day)
                        active_day_indices.append(str(day_idx))
                except Exception: continue

        if s_rev == 0: continue

        did_key = None if did == -1 else did
        res = (
            did_key, s_time, s_rev, s_pass, s_p_young, s_r_young, s_p_mat, s_r_mat,
            s_again, s_hard, s_good, s_easy, ",".join(active_day_indices)
        )
        results.append(res)

    return results, prev_stats_map, activity_map, retention_maps, bin_labels, bin_count







