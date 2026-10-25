# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from datetime import datetime

from ..builders import Period
from ...context_access import get_pinned_context
from ..utils import _addon_config
from .....logic.heatmap import get_heatmap_365_end_date, get_heatmap_year_end
from .....logic.data.transforms.heatmap_series import (
    build_heatmap_data,
    merge_heatmap_future_values,
)


def slice_heatmap_year_data(base_total, target_year):
    if not base_total:
        return None
    prefix = f"{target_year}-"
    return {k: v for k, v in base_total.items() if k.startswith(prefix)}


def build_heatmap_year_data(target_year, history, future_reviews=None, is_ready=False):
    if is_ready:
        return history, get_heatmap_year_end(target_year)

    heatmap_data, _ = build_heatmap_data(history)
    if future_reviews:
        merge_heatmap_future_values(heatmap_data, future_reviews, mode="set")
    return heatmap_data, get_heatmap_year_end(target_year)


def resolve_heatmap_year_from_context(target_year, ctx):
    if not isinstance(ctx, dict):
        return None, get_heatmap_year_end(target_year), "context_missing"

    if "heatmap_data" in ctx:
        return ctx["heatmap_data"], get_heatmap_year_end(target_year), "context_heatmap_data"

    if "reviews" in ctx:
        data, end = build_heatmap_year_data(
            target_year,
            ctx["reviews"],
            future_reviews=ctx.get("future_reviews", {}),
        )
        return data, end, "context_reviews"

    return None, get_heatmap_year_end(target_year), "context_empty"


def merge_heatmap_year_data(*data_chunks):
    merged = {}
    for data in data_chunks:
        if data:
            merged.update(data)
    return merged


def compose_heatmap_mode_data(target_year, mode, fetch_year_data, now=None):
    current_data, current_end = fetch_year_data(target_year)
    if current_data is None:
        return None, current_end

    if mode == "year":
        return current_data, current_end

    previous_data, _ = fetch_year_data(target_year - 1)
    merged = merge_heatmap_year_data(previous_data or {}, current_data)
    current_now = now or datetime.now()
    return merged, get_heatmap_365_end_date(target_year, now=current_now)


def fetch_missing_heatmap_years(years_needed, fetched_years, existing_data, fetch_year_data):
    missing = set(years_needed) - set(fetched_years)
    if not missing:
        return missing, None

    combined = dict(existing_data or {})
    for year in missing:
        year_data, _ = fetch_year_data(year)
        if year_data:
            combined.update(year_data)
            fetched_years.add(year)
    return missing, combined


def load_pinned_heatmap_year_data(
    deck_id,
    target_year,
    cfg=None,
    allow_slow_ops=True,
    total_heatmap_cache=None,
    year_data_cache=None,
    prefer_total_cache=False,
    missing_default=None,
):
    config = cfg or _addon_config()
    end = get_heatmap_year_end(target_year)
    # Several decks picked for the widget come as a list, which cannot be a dict key.
    deck_key = tuple(deck_id) if isinstance(deck_id, list) else deck_id
    cache_key = (deck_key, target_year) if year_data_cache is not None else None

    if cache_key is not None and cache_key in year_data_cache:
        return year_data_cache[cache_key], end, "year_cache"

    if prefer_total_cache and total_heatmap_cache is not None:
        if deck_key not in total_heatmap_cache:
            total_ctx = get_pinned_context(
                deck_id,
                Period.TOTAL,
                cfg=config,
                allow_slow_ops=allow_slow_ops,
            )
            if isinstance(total_ctx, dict) and "heatmap_data" in total_ctx:
                total_heatmap_cache[deck_key] = total_ctx["heatmap_data"]

        data = slice_heatmap_year_data(total_heatmap_cache.get(deck_key), target_year)
        if data is not None:
            if cache_key is not None:
                year_data_cache[cache_key] = data
            return data, end, "total_heatmap_cache"

    ctx = get_pinned_context(
        deck_id,
        target_year,
        cfg=config,
        allow_slow_ops=allow_slow_ops,
    )
    data, end, source = resolve_heatmap_year_from_context(target_year, ctx)
    if data is None:
        return missing_default, end, source

    if cache_key is not None:
        year_data_cache[cache_key] = data
    return data, end, source
