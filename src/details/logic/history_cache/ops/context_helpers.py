# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..shared import Period, datetime, mw, timedelta
from ...logger import log_swallowed


def resolve_lookup_id(instance, deck_id, cfg=None):
    lookup_id = deck_id
    if isinstance(deck_id, int) and deck_id != -1:
        try:
            if cfg and hasattr(cfg, "_deck_names"):
                name = cfg._deck_names.get(deck_id)
            else:
                name = mw.col.decks.name(deck_id)
            if name and name in instance.cache:
                lookup_id = name
        except Exception:
            log_swallowed()
    return lookup_id


def resolve_cache_key(range_type, custom_days=7, custom_type="relative", start_date_str="", end_date_str=""):
    if range_type == Period.CUSTOM:
        return (Period.CUSTOM, custom_days, custom_type, start_date_str, end_date_str)
    return range_type


def compute_slice_bounds(start_ms, end_ms, off_h):
    lb_date = (datetime.fromtimestamp(start_ms / 1000) - timedelta(hours=off_h)).strftime("%Y-%m-%d")
    ub_date = (datetime.fromtimestamp((end_ms - 1) / 1000) - timedelta(hours=off_h)).strftime("%Y-%m-%d")
    return lb_date, ub_date


def bisect_desc(arr, target_date, lo=0, hi=None):
    if hi is None:
        hi = len(arr)
    while lo < hi:
        mid = (lo + hi) // 2
        if arr[mid] > target_date:
            lo = mid + 1
        else:
            hi = mid
    return lo

