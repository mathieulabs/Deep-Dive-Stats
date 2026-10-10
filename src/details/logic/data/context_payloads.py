# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
LIST_HISTORY_TYPES = {"reviews", "added", "heatmap"}


def get_default_history_payload(history_type):
    return [] if history_type in LIST_HISTORY_TYPES else {}


_STREAK_MEMO = {}
_STREAK_MEMO_MAX = 64


def _memo_key(reviews):
    first, last = reviews[0], reviews[-1]
    if not (isinstance(first, dict) and isinstance(last, dict)):
        return None
    from .core.streaks import logical_today

    return (
        id(reviews),
        len(reviews),
        first.get("logical_date") or first.get("date", ""),
        last.get("logical_date") or last.get("date", ""),
        first.get("reviews", 0),
        logical_today().toordinal(),
    )


def context_stats(context):
    """Stats of a cache context, with the current streak counted again from its review days.

    The stored streak can be stale (cache saved on an earlier day, a day passed without
    reviews), so every reader should go through this.
    """
    if not isinstance(context, dict):
        return {}
    stats = context.get("stats", {})
    reviews = context.get("reviews")
    if isinstance(stats, dict) and isinstance(reviews, list) and reviews:
        from .core.streaks import current_streak_from_dates

        # Several widgets read the same context in one refresh: count it once.
        key = _memo_key(reviews)
        streak = _STREAK_MEMO.get(key) if key is not None else None
        if streak is None:
            dates = [
                r.get("logical_date") or r.get("date", "")
                for r in reviews
                if isinstance(r, dict) and (r.get("reviews") or 0) > 0
            ]
            streak = current_streak_from_dates(dates)
            if key is not None:
                if len(_STREAK_MEMO) >= _STREAK_MEMO_MAX:
                    _STREAK_MEMO.clear()
                _STREAK_MEMO[key] = streak
        stats = dict(stats)
        stats["streak"] = streak
    return stats


def get_context_history_payload(
    context,
    history_type,
    *,
    heatmap_mode="resolved",
    future_key="future_reviews",
):
    if not isinstance(context, dict):
        return None

    if history_type == "reviews":
        return context.get("reviews")
    if history_type == "added":
        return context.get("added")
    if history_type == "card_counts":
        return context.get("counts")
    if history_type == "distribution":
        return context.get("distribution")
    if history_type == "heatmap":
        if heatmap_mode == "cache_probe":
            return context.get("heatmap_data")
        if heatmap_mode == "raw_reviews":
            return context.get("reviews", [])
        return context.get("heatmap_data") or context.get("reviews")
    if history_type == "heatmap_data":
        return context.get("heatmap_data", {})
    if history_type == "future_reviews":
        return context.get(future_key, {})
    if history_type == "stats":
        return context_stats(context)

    return context.get(history_type)
