# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from ..utils import _history, _addon_config, _get_max_ids, cache_data_version
from . import Config, Period, get_color
from .....logic.data.section_fetchers import fetch_section_data
from ....stats_cards import (
    build_dashboard_history_totals,
    resolve_effective_stat_card_config,
    get_stat_card_info,
    map_stat_fields_to_config_keys,
    build_dashboard_stat_values,
    HISTORY_DERIVED_STAT_KEYS,
    DECK_STATE_STAT_KEYS,
    deck_state_from_context,
)
from ...context_access import get_pinned_context
from .....logic.data.section_fallbacks import resolve_card_counts_payload


_STAT_VALUE_CACHE = {}

def _time_stat_fields():
    from ....stats_cards.logic.model import STAT_VALUE_FIELD_BINDINGS
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
    return (excluded, include_deleted, today, col_id)


def _prune_stat_value_cache():
    if len(_STAT_VALUE_CACHE) > 64:
        _STAT_VALUE_CACHE.clear()


def _effective_stat_card_config(widget_def, cfg=None):
    """Return effective style config for stat cards (global + optional unlinked overrides)."""
    base_cfg = cfg.config if cfg is not None else _addon_config().config
    return resolve_effective_stat_card_config(base_cfg, widget_def)


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
        if not history:
            if fail_if_not_cached:
                return None
            result = {}
            _prune_stat_value_cache()
            _STAT_VALUE_CACHE[cache_key] = result
            return result
        totals_payload = build_dashboard_history_totals(history, streak_current=0)

    if with_deck_state:
        state = deck_state_from_context(get_pinned_context(deck_id, Period.TOTAL, cfg=cfg, allow_slow_ops=False))
        totals_payload.update(state)
        totals_payload["counts"] = resolve_card_counts_payload(
            {"counts": state["counts"]} if state["counts"] is not None else None,
            fetcher=None if fail_if_not_cached else (lambda: fetch_section_data(cfg, "card_counts", deck_id=deck_id)),
            fetch_when_empty=False,
            fetch_when_non_deleted_zero_total=False,
        )

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
    result["_raw_avg_time_s"] = (_hours * 3600.0 / _revs) if _revs > 0 else None
    _prune_stat_value_cache()
    _STAT_VALUE_CACHE[cache_key] = result
    return result


def _get_stat_info(widget_def, deck_id, cache=None, fail_if_not_cached=False, cfg=None):
    stat_key = widget_def.get("stat_key")
    title, fallback_color = get_stat_card_info(stat_key)

    from .....ui import STAT_KEY_TO_COLOR_KEY

    if cfg is None:
        cfg = _addon_config()
    color_key = STAT_KEY_TO_COLOR_KEY.get(stat_key)
    if color_key:
        base_color = get_color(cfg.config, color_key, "pinned")
    else:
        base_color = fallback_color

    span = widget_def.get("time_span", Period.TOTAL)
    days = widget_def.get("custom_days", 7)
    stat_values = _build_stat_values_map(
        deck_id,
        span,
        days,
        cache=cache,
        fail_if_not_cached=fail_if_not_cached,
        cfg=cfg,
        with_day_stats=stat_key in HISTORY_DERIVED_STAT_KEYS,
        with_deck_state=stat_key in DECK_STATE_STAT_KEYS,
    )
    if stat_values is None:
        return None
    custom_label = widget_def.get("label")
    if custom_label is not None:
        title = custom_label if str(custom_label).strip() else ""

    if not stat_values:
        return (title, "...", base_color)

    value = stat_values.get(stat_key, "...")
    field = TIME_STAT_FIELDS.get(stat_key)
    unit = widget_def.get("time_unit")
    if field and unit and unit != "auto":
        from .time_units import apply_time_unit
        converted = apply_time_unit(field, unit, stat_values, int(cfg.config.get(Config.STATS_PRECISION, 2)))
        if converted is not None:
            value = converted
    return (title, value, base_color)


def _build_stat_card(widget_def, deck_id, cache=None, parent=None, cfg=None):
    info = _get_stat_info(widget_def, deck_id, cache=cache, cfg=cfg)

    wid = widget_def.get("id")
    from ....stats_cards import StatCardWidget

    if not info:
        info = ("Loading...", "...", "#808080")

    effective_conf = _effective_stat_card_config(widget_def, cfg=cfg)
    title, value, color = info
    stat_key = widget_def.get("stat_key")
    span = widget_def.get("time_span", Period.TOTAL)
    card = StatCardWidget(
        title,
        value,
        color=color,
        is_pinned=True,
        widget_id=wid,
        parent=parent,
        config_key=stat_key,
        deck_id=deck_id,
        time_span=span,
        addon_config=effective_conf,
    )
    card.set_centered(True)
    if not str(title).strip():
        card.set_title_visible(False)

    return card


def _update_stat_card(widget, widget_def, deck_id, cache=None, fail_if_not_cached=False, cfg=None):
    info = _get_stat_info(widget_def, deck_id, cache=cache, fail_if_not_cached=fail_if_not_cached, cfg=cfg)
    if info is None:
        return False

    effective_conf = _effective_stat_card_config(widget_def, cfg=cfg)
    title, value, color = info
    payload_sig = (title, str(value), str(color), deck_id, effective_conf)
    if getattr(widget, "_last_stat_runtime_payload", None) == payload_sig:
        return True

    widget.addon_config = effective_conf
    if hasattr(widget, "update_val"):
        widget.update_val(value, color=color, title=title, deck_id=deck_id)
        widget._last_stat_runtime_payload = payload_sig
        return True
    return False
