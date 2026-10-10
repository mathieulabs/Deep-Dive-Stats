# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..utils import _addon_config, _history
from ..builders import Period
from .context import get_pinned_context
from .....logic.data.section_fetchers import fetch_section_data
from .....logic.data.transforms.activity_series import (
    build_activity_series,
    build_breakdown_rows,
    filter_activity_types,
    normalize_hidden_types,
)
from .....logic.data.transforms.retention_series import (
    RETENTION_SERIES_KEYS,
    build_retention_series,
)


def is_direct_review_range(span):
    try:
        return span is not None and int(span) in (int(Period.TODAY), int(Period.YESTERDAY))
    except Exception:
        return False


def load_oldest_first_section_history(
    deck_id,
    span,
    section_type,
    cache=None,
    cfg=None,
    custom_days=7,
    fail_if_not_cached=False,
):
    if is_direct_review_range(span):
        config = cfg or _addon_config()
        history_desc = fetch_section_data(config, section_type, deck_id=deck_id, range_type=int(span)) or []
        return {
            "history_desc": history_desc,
            "oldest_first": history_desc[::-1],
            "history_is_none": False,
        }

    history_desc = _history(
        deck_id,
        range_type=span,
        cache=cache,
        history_type=section_type,
        fail_if_not_cached=fail_if_not_cached,
        cfg=cfg,
        custom_days=custom_days,
    )
    history_is_none = history_desc is None
    history_desc = history_desc or []
    return {
        "history_desc": history_desc,
        "oldest_first": history_desc[::-1],
        "history_is_none": history_is_none,
    }


def load_oldest_first_review_history(
    deck_id,
    span,
    cache=None,
    cfg=None,
    custom_days=7,
    fail_if_not_cached=False,
):
    return load_oldest_first_section_history(
        deck_id,
        span,
        "reviews",
        cache=cache,
        cfg=cfg,
        custom_days=custom_days,
        fail_if_not_cached=fail_if_not_cached,
    )


def load_activity_source(
    deck_id,
    span,
    cache=None,
    cfg=None,
    custom_days=7,
    fail_if_not_cached=False,
    allow_context_slow_ops=False,
    hidden_types=None,
):
    """Activity data of a widget, without the review types it hides."""
    source = _load_activity_source(
        deck_id,
        span,
        cache=cache,
        cfg=cfg,
        custom_days=custom_days,
        fail_if_not_cached=fail_if_not_cached,
        allow_context_slow_ops=allow_context_slow_ops,
    )
    hidden = normalize_hidden_types(hidden_types)
    if hidden and source.get("raw_hist") is not None:
        source = dict(source)
        raw = filter_activity_types(source["raw_hist"], hidden)
        source["raw_hist"] = raw
        if source.get("breakdown_data") is not None:
            source["breakdown_data"] = filter_activity_types(source["breakdown_data"], hidden)
        source["activity_data"] = build_activity_series(raw)
    return source


def _load_activity_source(
    deck_id,
    span,
    cache=None,
    cfg=None,
    custom_days=7,
    fail_if_not_cached=False,
    allow_context_slow_ops=False,
):
    if is_direct_review_range(span):
        history_bundle = load_oldest_first_review_history(
            deck_id,
            span,
            cache=cache,
            cfg=cfg,
            custom_days=custom_days,
            fail_if_not_cached=False,
        )
        oldest_first = history_bundle["oldest_first"]
        return {
            "activity_data": build_activity_series(oldest_first),
            "breakdown_data": build_breakdown_rows(oldest_first, count_key_style="plain"),
            "raw_hist": oldest_first,
            "history_is_none": False,
        }

    ctx = get_pinned_context(
        deck_id,
        span,
        cfg=cfg,
        custom_days=custom_days,
        fail_if_not_cached=fail_if_not_cached,
        allow_slow_ops=allow_context_slow_ops,
    )
    if ctx and "activity_data" in ctx:
        return {
            "activity_data": ctx["activity_data"],
            "breakdown_data": ctx.get("activity_breakdown"),
            "raw_hist": list(reversed(ctx.get("reviews", []))),
            "history_is_none": False,
        }

    if cache and "activity_data" in cache:
        return {
            "activity_data": cache["activity_data"],
            "breakdown_data": cache.get("activity_breakdown"),
            "raw_hist": list(reversed(cache.get("reviews", []))),
            "history_is_none": False,
        }

    history_bundle = load_oldest_first_review_history(
        deck_id,
        span,
        cache=cache,
        cfg=cfg,
        custom_days=custom_days,
        fail_if_not_cached=fail_if_not_cached,
    )
    oldest_first = history_bundle["oldest_first"]
    return {
        "activity_data": build_activity_series(oldest_first),
        "breakdown_data": build_breakdown_rows(oldest_first, count_key_style="plain"),
        "raw_hist": oldest_first,
        "history_is_none": history_bundle["history_is_none"],
    }


def load_retention_source(
    deck_id,
    span,
    cache=None,
    cfg=None,
    custom_days=7,
    fail_if_not_cached=False,
):
    if is_direct_review_range(span):
        history_bundle = load_oldest_first_review_history(
            deck_id,
            span,
            cache=cache,
            cfg=cfg,
            custom_days=custom_days,
            fail_if_not_cached=False,
        )
        oldest_first = history_bundle["oldest_first"]
        return {
            "retention_data": build_retention_series(oldest_first, strict_series=RETENTION_SERIES_KEYS),
            "raw_hist": oldest_first,
            "history_is_none": False,
        }

    if cache and "retention_data" in cache:
        return {
            "retention_data": cache["retention_data"],
            "raw_hist": list(reversed(cache.get("reviews", []))),
            "history_is_none": False,
        }

    history_bundle = load_oldest_first_review_history(
        deck_id,
        span,
        cache=cache,
        cfg=cfg,
        custom_days=custom_days,
        fail_if_not_cached=fail_if_not_cached,
    )
    oldest_first = history_bundle["oldest_first"]
    return {
        "retention_data": build_retention_series(oldest_first, strict_series=RETENTION_SERIES_KEYS),
        "raw_hist": oldest_first,
        "history_is_none": history_bundle["history_is_none"],
    }


def load_added_source(
    deck_id,
    span,
    cache=None,
    cfg=None,
    custom_days=7,
    fail_if_not_cached=False,
):
    history_bundle = load_oldest_first_section_history(
        deck_id,
        span,
        "added",
        cache=cache,
        cfg=cfg,
        custom_days=custom_days,
        fail_if_not_cached=fail_if_not_cached,
    )
    return {
        "history_desc": history_bundle["history_desc"],
        "oldest_first": history_bundle["oldest_first"],
        "history_is_none": history_bundle["history_is_none"],
    }


def load_distribution_source(
    deck_id,
    span,
    cache=None,
    cfg=None,
    custom_days=7,
    fail_if_not_cached=False,
):
    distribution_data = _history(
        deck_id,
        range_type=span,
        cache=cache,
        history_type="distribution",
        fail_if_not_cached=fail_if_not_cached,
        cfg=cfg,
        custom_days=custom_days,
    )
    history_is_none = distribution_data is None
    return {
        "distribution_data": distribution_data or {},
        "history_is_none": history_is_none,
    }
