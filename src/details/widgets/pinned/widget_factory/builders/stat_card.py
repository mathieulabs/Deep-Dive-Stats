# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from ..utils import _history, _addon_config, _get_max_ids, cache_data_version
from . import Config, Period
from .....logic.data.section_fetchers import fetch_section_data
from ....stats_cards import (
    build_dashboard_history_totals, map_stat_fields_to_config_keys, build_dashboard_stat_values, deck_state_from_context,
)
from ...context_access import get_pinned_context
from .....logic.data.section_fallbacks import resolve_card_counts_payload


_STAT_VALUE_CACHE = {}

def _time_stat_fields():
    from .....logic.stat_cards import STAT_VALUE_FIELD_BINDINGS
    from .time_units import TIME_RAW
    out = {}
    for field, dd_key, dash_key in STAT_VALUE_FIELD_BINDINGS:
        if field in TIME_RAW:
            out[dash_key] = field
            if dd_key:
                out[dd_key] = field
    return out


TIME_STAT_FIELDS = _time_stat_fields()


def _stat_context_token(cfg):
    try:
        conf = cfg.config
        excluded = tuple(sorted(str(x) for x in (conf.get(Config.EXCLUDED_DECKS, []) or [])))
        include_deleted = bool(conf.get(Config.INCLUDE_DELETED_CARDS, True))
        excluded += tuple(str(x) for x in (conf.get(Config.EXCLUDED_DATES, []) or []))
    except Exception:
        excluded, include_deleted = (), True
    try:
        from aqt import mw

        today = int(mw.col.sched.today)
        col_id = id(mw.col)
    except Exception:
        today, col_id = 0, 0
    try:
        from .....logic.search_filter import active_search_query
        search_q = active_search_query()
    except Exception:
        search_q = ""
    return (excluded, include_deleted, today, col_id, search_q)


def _prune_stat_value_cache():
    if len(_STAT_VALUE_CACHE) > 64:
        _STAT_VALUE_CACHE.clear()


def _build_stat_values_map(
    deck_id,
    span,
    days,
    *,
    cache=None,
    fail_if_not_cached=False,
    cfg=None,
    custom_type="relative",
    start_date_str="",
    end_date_str="",
    with_day_stats=False,
    with_deck_state=False,
):
    """with_day_stats: also read the daily history (days learned, longest streak, best day, per-day averages)."""
    if cfg is None:
        cfg = _addon_config()

    max_ids = _get_max_ids(allow_db=not fail_if_not_cached)
    precision = int(cfg.config.get(Config.STATS_PRECISION, 2))
    is_direct_review_range = int(span) in (int(Period.TODAY), int(Period.YESTERDAY))
    cache_key = (
        tuple(deck_id) if isinstance(deck_id, list) else deck_id,
        int(span),
        int(days),
        str(custom_type or "relative"),
        str(start_date_str or ""),
        str(end_date_str or ""),
        bool(with_day_stats),
        bool(with_deck_state),
        # Direct ranges read SQL whatever the flag, so share one entry (lets a
        # background prewarm serve the main thread).
        bool(fail_if_not_cached) and not is_direct_review_range,
        max_ids,
        cache_data_version(),
        precision,
        bool(cfg.config.get(Config.USE_THOUSANDS_SEPARATOR, True)),
        # Settings and the Anki day change what a number means without a new review:
        # excluded decks, deleted reviews, and "Today"/"Yesterday" after the day rolls
        # over while Anki stays open.
        _stat_context_token(cfg),
    )
    if cache_key in _STAT_VALUE_CACHE:
        return _STAT_VALUE_CACHE[cache_key]

    if is_direct_review_range:
        stats = fetch_section_data(
            cfg,
            "stats",
            deck_id=deck_id,
            range_type=span,
            custom_days=days,
            custom_type=custom_type,
            start_date_str=start_date_str,
            end_date_str=end_date_str,
        )
    else:
        stats = _history(
            deck_id,
            span,
            history_type="stats",
            cache=cache,
            fail_if_not_cached=fail_if_not_cached,
            cfg=cfg,
            custom_days=days,
            custom_type=custom_type,
            start_date_str=start_date_str,
            end_date_str=end_date_str,
        )

    if stats:
        totals_payload = {
            "time": stats.get("total_time_ms", 0) / (1000 * 3600),
            "rev": stats.get("total_reviews", 0),
            "pass": stats.get("total_passed", 0),
            "pass_young": stats.get("pass_young", 0),
            "rev_young": stats.get("rev_young", 0),
            "pass_mat": stats.get("pass_mat", 0),
            "rev_mat": stats.get("rev_mat", 0),
            "streak_current": stats.get("streak", 0),
            "active_days": stats.get("active_days", 0),
            "again": stats.get("again"),
        }
        if with_day_stats:
            day_history = _history(
                deck_id,
                range_type=span,
                cache=cache,
                fail_if_not_cached=fail_if_not_cached,
                custom_days=days,
                custom_type=custom_type,
                start_date_str=start_date_str,
                end_date_str=end_date_str,
            )
            if day_history:
                day_totals = build_dashboard_history_totals(day_history)
                for key in ("days_in_period", "period_active_days", "longest_streak", "best_day"):
                    totals_payload[key] = day_totals[key]
    else:
        history = _history(
            deck_id,
            range_type=span,
            cache=cache,
            fail_if_not_cached=fail_if_not_cached,
            custom_days=days,
            custom_type=custom_type,
            start_date_str=start_date_str,
            end_date_str=end_date_str,
        )
        if not history and fail_if_not_cached:
            return None
        # No stats in the cache (it is being refreshed): count the streak from the review days.
        # No history at all is a deck without reviews: its numbers are zeros (a stat card
        # showed "..." and a text widget its raw {variables}).
        from .....logic.data.core.streaks import current_streak_from_dates

        history = history or []
        streak = current_streak_from_dates(
            [h.get("logical_date") or h.get("date", "") for h in history if (h.get("reviews") or 0) > 0]
        )
        totals_payload = build_dashboard_history_totals(history, streak_current=streak)

    if with_deck_state:
        state = deck_state_from_context(get_pinned_context(deck_id, Period.TOTAL, cfg=cfg, allow_slow_ops=False))
        totals_payload.update(state)
        totals_payload["counts"] = resolve_card_counts_payload(
            {"counts": state["counts"]} if state["counts"] is not None else None,
            fetcher=None if fail_if_not_cached else (lambda: fetch_section_data(cfg, "card_counts", deck_id=deck_id)),
            fetch_when_empty=False,
            fetch_when_non_deleted_zero_total=False,
        )

    # Streak and Longest Streak: over the whole history, whatever the period (a 200-day streak read 0 on "Today",
    # and a record of at most 7 on "Week"); the current one still counts yesterday while today has no review yet.
    if int(span) != int(Period.TOTAL):
        whole = _history(deck_id, range_type=Period.TOTAL, cache=cache, fail_if_not_cached=fail_if_not_cached, cfg=cfg)
        if whole:
            from .....logic.data.core.streaks import current_streak_from_dates
            from .....logic.stat_cards import history_day_stats

            totals_payload["streak_current"] = current_streak_from_dates(
                [h.get("logical_date") or h.get("date", "") for h in whole if (h.get("reviews") or 0) > 0]
            )
            totals_payload["longest_streak"] = history_day_stats(whole)["longest_streak"]

    values_by_field = build_dashboard_stat_values(
        totals_payload,
        use_decimal=True,
        hrs_unit="h",
        min_unit=" min",
        prec=precision,
        time_precision=precision,
    )
    result = map_stat_fields_to_config_keys(values_by_field)
    # Raw numbers so text widgets can show time in the unit they ask for.
    _hours = float(totals_payload.get("time", 0) or 0.0)
    _days = totals_payload.get("days_in_period") or 0
    _revs = totals_payload.get("rev", 0) or 0
    result["_raw_total_time_h"] = _hours
    result["_raw_time_per_day_h"] = (_hours / _days) if _days > 0 else None
    from .....logic.stat_cards import active_days_of

    _active = active_days_of(totals_payload)
    result["_raw_time_per_active_day_h"] = (_hours / _active) if _active > 0 else None
    result["_raw_avg_time_s"] = (_hours * 3600.0 / _revs) if _revs > 0 else None
    _prune_stat_value_cache()
    _STAT_VALUE_CACHE[cache_key] = result
    return result


