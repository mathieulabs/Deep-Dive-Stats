# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Data of each chart type, as plain JSON."""

_TYPES = ("mature", "young", "relearn", "learn", "cram")


def _row_start(r):
    """(start ms, length ms) of a history row: a day from its rollover hour ("YYYY-MM-DD"), or a 10-minute row
    ("YYYY-MM-DD HH:MM"); (None, None) when it has no such date."""
    from datetime import datetime

    s = str(r.get("date") or r.get("logical_date") or "")
    try:
        return int(datetime.strptime(s, "%Y-%m-%d %H:%M").timestamp() * 1000), 600000
    except ValueError:
        pass
    try:
        from ..utils import rollover_hour

        return int(datetime.strptime(s, "%Y-%m-%d").replace(hour=rollover_hour()).timestamp() * 1000), 86400000
    except Exception:
        return None, None


def _num(v):
    """Compact JSON number: int when whole (42 instead of 42.0), else rounded float."""
    f = float(v)
    i = int(f)
    return i if f == i else round(f, 3)


def _daily_rows(breakdown, raw=None):
    # raw: the history rows they come from; each row then carries its start time (t, ms) and length (dt, ms), so the
    # page can lay the days, the 10-minute rows and the single reviews on one time line (their axes slide between them)
    starts = {}
    for src in raw or []:
        lab = str((src or {}).get("pretty_date", "") or "")
        if lab and lab not in starts:
            starts[lab] = _row_start(src)
    rows = []
    for r in breakdown or []:
        row = {"date": str(r.get("pretty_date", "") or "")}
        rv = r.get("reviews", 0) or 0
        if rv:
            row["reviews"] = _num(rv)
        tm = r.get("time_ms", 0) or 0
        if tm:
            row["time_ms"] = _num(tm)
        t, dt = starts.get(row["date"], (None, None))
        if t is not None:
            row["t"] = t
            row["dt"] = dt
        for k in _TYPES:
            v = r.get(k, 0) or 0
            if v:
                row[k] = _num(v)
            vt = r.get(k + "_time_ms", 0) or 0
            if vt:
                row[k + "_time_ms"] = _num(vt)
        rows.append(row)
    return rows


def activity(deck, span, options=None):
    from ..details.logic.data.transforms.activity_series import attach_breakdown_totals
    from ..details.widgets.pinned.widget_factory.shared.reviews import load_activity_source

    source = load_activity_source(
        deck, span, cache=None, cfg=_cfg(), custom_days=_custom_days(options),
        fail_if_not_cached=False, allow_context_slow_ops=True,
    )
    breakdown = source.get("breakdown_data")
    if breakdown is None:
        return {"rows": []}
    return {"rows": _daily_rows(attach_breakdown_totals(breakdown, source["raw_hist"]), source["raw_hist"])}


def anim_settings(context="details", conf=None):
    """Settings > General > Animations for a page: {on, appear, zoom, style} (dd-core.js DD.setAnim). Animation
    Mode turns the window's ("details") or the pinned widgets' ("pinned") animations off; the transition style is
    each page's own."""
    from ..const.config import Config

    c = conf if conf is not None else _cfg().config
    scope = str(c.get(Config.ANIMATION_SCOPE, "all") or "all").strip().lower()
    on = scope == "all" or (scope == "no_pinned" and context != "pinned") or (scope == "no_details" and context == "pinned")
    key = Config.PINNED_TRANSITION_STYLE if context == "pinned" else Config.DEEP_DIVE_TRANSITION_STYLE
    style = str(c.get(key, "morph") or "morph").strip().lower()
    # Animation Speed: every duration of the page's charts times this
    speed_key = Config.PINNED_ANIMATION_SPEED if context == "pinned" else Config.DEEP_DIVE_ANIMATION_SPEED
    speed = ANIMATION_SPEEDS.get(str(c.get(speed_key, "normal") or "normal").strip().lower(), 1.0)
    return {"on": bool(on), "appear": bool(c.get(Config.CHART_APPEAR_ANIMATION, True)),
            "zoom": bool(c.get(Config.ZOOM_ANIMATION, True)), "style": style if style in ("morph", "fade", "none") else "morph",
            "speed": speed}


# Settings > General > Animations, "Animation Speed": a factor on the durations (Slow: 1.5x as long)
ANIMATION_SPEEDS = {"slow": 1.5, "normal": 1.0, "fast": 0.6}


def widget_options(chart_type, own=None, conf=None):
    """_widget_options, with the chart look shared by every chart (Settings > General > Chart Style, or the widget's
    own Chart Appearance): the total / average lines' opacity, the bars' gradient, the grid lines. The web charts
    drew them at their defaults whatever the settings said."""
    from ..const.config import Config

    out = _widget_options(chart_type, own, conf)
    if not isinstance(out, dict):
        return out
    c = conf if conf is not None else _cfg().config
    if own is not None:
        sets = own
    else:
        sets = dict((c.get(Config.DEEP_DIVE_WIDGET_SETTINGS) or {}).get(chart_type + "_g") or {})
        sets.update(_preview_sets(chart_type))

    def pick(key, conf_key, default):
        v = sets.get(key)
        return c.get(conf_key, default) if v is None else v

    try:
        out.setdefault("line_opacity_pct", int(pick("line_opacity", Config.CHART_LINE_OPACITY, 80)))
        out.setdefault("bar_gradient_pct", int(pick("bar_gradient", Config.CHART_BAR_GRADIENT, 43)))
        out.setdefault("total_line_pct", max(0, min(100, int(pick("total_line", Config.CHART_TOTAL_LINE, 0) or 0))))
        out.setdefault("show_grid", bool(pick("show_grid", Config.CHART_SHOW_GRID, True)))
        if own is not None and own.get("custom_days"):
            out.setdefault("custom_days", int(own["custom_days"]))
    except (TypeError, ValueError):
        pass
    return out


def _widget_options(chart_type, own=None, conf=None):
    """Options of a chart, read from the config.
    own: a pinned widget's definition, whose keys are its settings (the pinned builders read the same names)."""
    from ..const.config import Config

    conf = conf if conf is not None else _cfg().config  # a settings dialog's live preview passes its copy
    _root = conf.get(Config.DEEP_DIVE_WIDGET_SETTINGS) or {}
    if own is not None:
        sets = dict(own)
        if "breakdown_enabled" not in sets and "show_breakdown" in sets:
            sets["breakdown_enabled"] = sets["show_breakdown"]
    else:
        sets = dict(_root.get(chart_type + "_g") or {})
        _mgr = _root.get("manager_g") or _root.get("manager") or {}
        for _k in ("show_average", "avg_on_active_days", "show_cumulative"):  # the header gear menu's global choices
            if _k not in sets and _k in _mgr:
                sets[_k] = _mgr[_k]
        sets.update(_preview_sets(chart_type))
    if chart_type == "activity":
        opacity = sets.get("chart_opacity", 100)
        return {
            "metric_mode": "time" if sets.get("show_time_axis", False) else "reviews",
            "show_average": bool(sets.get("show_average", True)),
            "avg_on_active_days": bool(sets.get("avg_on_active_days", True)),
            "show_cumulative": bool(sets.get("show_cumulative", True)),
            "show_breakdown": bool(sets.get("breakdown_enabled", True)),
            "adaptive_binning": bool(conf.get(Config.ADAPTIVE_CHART_BINNING, True)) if sets.get("binning_override") is None else bool(sets.get("binning_override")),
            "show_percent": bool(sets.get("show_percent", False)),
            "show_trend": bool(sets.get("show_trend", False)),
            "hidden_review_types": list(sets.get("hidden_review_types") or []),
            "chart_opacity_pct": 100 if opacity is None else opacity,
        }
    if chart_type == "retention":
        dd = conf.get(Config.DEEP_DIVE_WIDGET_SETTINGS) or {}
        vis = {"all": False, "young": True, "mature": True}
        vis.update(sets.get("visibility") or (dd.get("retention") or {}).get("visibility") or {})
        override = sets.get("binning_override")
        opacity = sets.get("chart_opacity", 100)
        return {
            "visible": vis,
            "fit_to_data": bool(sets.get("fit_to_data", False)),
            "binning": bool(conf.get(Config.ADAPTIVE_CHART_BINNING, True)) if override is None else bool(override),
            "min_reviews": int(sets.get("min_reviews", 0) or 0),
            "review_bars": bool(sets.get("review_bars", True)),
            "review_axis": bool(sets.get("review_axis", False)),
            "rounded": bool(sets.get("rounded", True)),
            "chart_opacity_pct": 100 if opacity is None else opacity,
        }
    if chart_type == "added":
        override = sets.get("binning_override")
        return {
            "sync_zoom": bool(sets.get("sync_zoom", True)),
            "show_trend": bool(sets.get("show_trend", False)),
            "adaptive_binning": bool(conf.get(Config.ADAPTIVE_CHART_BINNING, True)) if override is None else bool(override),
        }
    if chart_type in ("ratings", "review_speed", "forgotten", "resets", "introduced", "introduced_load", "answer_time", "interval_ratings",
                      "rating_fatigue", "sibling_ratings", "card_states", "load_trend", "stability_trend", "memorised", "fsrs_calibration", "forgetting_curve", "fsrs_fatigue", "leech_detector", "stability_increase", "custom_bar", "future_retention", "due_today"):
        override = sets.get("binning_override")
        opacity = sets.get("chart_opacity", 100)
        return {
            "show_average": bool(sets.get("show_average", True)),
            "avg_on_active_days": bool(sets.get("avg_on_active_days", True)),
            "show_cumulative": bool(sets.get("show_cumulative", True)),
            "show_percent": bool(sets.get("show_percent", chart_type == "future_retention")),
            "show_trend": bool(sets.get("show_trend", True)),
            "show_breakdown": bool(sets.get("show_breakdown", True)),
            "alt_view": bool(sets.get("alt_view", chart_type == "card_states")),  # Card Counts over Time: split by type by default
            "first_reintro": bool(sets.get("first_reintro", True)),  # Introduced: the cards introduced again counted
            "variation": bool(sets.get("variation", False)),  # the level charts: the change of each bar
            "line_view": bool(sets.get("line_view", False)),  # the level charts and averages: a line, not bars
            "hidden_series": list(sets.get("hidden_series") or []),
            "adaptive_binning": bool(conf.get(Config.ADAPTIVE_CHART_BINNING, True)) if override is None else bool(override),
            "chart_opacity_pct": 100 if opacity is None else opacity,
        }
    if chart_type == "todays_retention":
        # its header and menu choices: a pinned widget whose choice changes in Anki's menu reads its data again
        # (pinned.js: other options, the data asked again)
        return {"card_type": sets.get("card_type") or "all", "show_change": sets.get("show_change", True) is not False,
                "show_target": sets.get("show_target", True) is not False, "legend_mode": sets.get("legend_mode") or "auto"}
    if chart_type == "card_counts":
        return {"legend_mode": sets.get("legend_mode") or "auto", "show_legend": sets.get("show_legend", True) is not False}
    if chart_type in ("week_hours", "sxr_heatmap"):
        opacity = sets.get("chart_opacity", 100)
        return {"chart_opacity_pct": 100 if opacity is None else opacity}
    if chart_type in ("future_due", "review_intervals", "stability", "difficulty", "retrievability", "interval_load",
                      "lapse_distribution", "review_distribution", "learning_steps", "time_distribution", "interval_history",
                      "stability_history", "difficulty_history"):
        override = sets.get("binning_override")
        opacity = sets.get("chart_opacity", 100)
        return {
            "show_cumulative": bool(sets.get("show_cumulative", True)),
            "pie_view": bool(sets.get("pie_view", False)),  # the distribution charts: as a pie (discrete.js)
            "hidden_series": list(sets.get("hidden_series") or []),
            "adaptive_binning": bool(conf.get(Config.ADAPTIVE_CHART_BINNING, True)) if override is None else bool(override),
            "chart_opacity_pct": 100 if opacity is None else opacity,
        }
    if chart_type == "heatmap":
        from ..const.theme.color_resolver import get_color
        from ..details.widgets.charts.heatmap.palettes import NO_FLIP, PRESET_COLORS, colors_of, customs_of, palette_of

        style = dict(conf)
        if own is not None:  # a pinned heatmap: the global heatmap settings, each one its entry has over them
            style.update(sets)  # (builders/heatmap._apply_heatmap_widget_settings: any Heatmap_* key of the entry)
        else:
            style.update(sets if sets.get("use_custom_style", False) else (conf.get(Config.DEEP_DIVE_GRID_STYLE) or {}))
        try:
            from datetime import datetime, timedelta

            from ..utils import rollover_hour

            logical_today = (datetime.now() - timedelta(hours=rollover_hour())).date().isoformat()
        except Exception:
            from datetime import date

            logical_today = date.today().isoformat()
        today = logical_today
        src = style if own is not None else conf
        mode = sets.get("heatmap_mode", "year")
        if mode not in ("year", "365", "continuous", "years"):
            mode = "year"
        return {
            "color": get_color(style if own is not None else conf, Config.HEATMAP_COLOR, "pinned" if own is not None else "details"),
            "monday_first": bool(style.get(Config.HEATMAP_MONDAY_FIRST, False)),
            "empty_opacity": style.get(Config.HEATMAP_EMPTY_OPACITY, 15),
            "filled_opacity": style.get(Config.HEATMAP_FILLED_OPACITY, 100),
            "empty_white": bool(style.get(Config.HEATMAP_EMPTY_WHITE, False)),
            "hide_labels": bool(style.get(Config.HEATMAP_HIDE_LABELS, False)),
            "tinted_future": bool(style.get(Config.HEATMAP_TINTED_FUTURE, False)),
            "show_future": bool(src.get(Config.HEATMAP_SHOW_FUTURE, True)),
            "scale": (style.get(Config.HEATMAP_SCALE, 100) or 100) / 100.0,
            "color_levels": style.get(Config.HEATMAP_COLOR_LEVELS, 15),
            "vibrance": style.get(Config.HEATMAP_VIBRANCE, 100),
            "rounding": style.get(Config.HEATMAP_ROUNDING, 20),
            "intensity_curve": style.get(Config.HEATMAP_INTENSITY_CURVE, 100),
            "multi_hue": bool(src.get(Config.HEATMAP_MULTI_HUE_INTENSITY, False)),
            "palette": palette_of(src.get),
            "palette_colors": colors_of(src.get),
            "custom_palettes": customs_of(src.get),
            "preset_colors": PRESET_COLORS,
            "preset_noflip": list(NO_FLIP),
            "metric": src.get(Config.HEATMAP_METRIC, "reviews"),
            "show_legend": bool(style.get(Config.HEATMAP_SHOW_LEGEND, True)),
            "show_mode_365": bool(src.get(Config.HEATMAP_SHOW_365_MODE, True)),
            "show_mode_cont": bool(src.get(Config.HEATMAP_SHOW_CONTINUOUS_MODE, True)),
            "show_mode_year": bool(src.get(Config.HEATMAP_SHOW_YEAR_MODE, True)),
            "show_mode_years": bool(src.get(Config.HEATMAP_SHOW_YEARS_MODE, True)),
            "click_browser": bool(src.get(Config.HEATMAP_CLICK_BROWSER, True)),
            "invert": bool(src.get(Config.HEATMAP_INVERT_INTENSITY, False)),
            "years_no_gap": bool(src.get(Config.HEATMAP_YEARS_NO_GAP, False)),
            "month_grid": bool(src.get(Config.HEATMAP_MONTH_GRID, False)),
            "narrow_view": conf.get(Config.HEATMAP_NARROW_VIEW, "") or "",  # global, as the button saves it
            # on a narrow card, the year in two rows or the month grid; None: on a phone only (heatmap.js narrowOn)
            "narrow_layout": sets.get("narrow_layout", True if own is not None else None),
            "years_fold": int(src.get(Config.HEATMAP_YEARS_FOLD, 3) if src.get(Config.HEATMAP_YEARS_FOLD, 3) is not None else 3),
            "mode": mode,
            "today": today,
            "logical_today": logical_today,
        }
    opacity = sets.get("chart_opacity", 100)
    return {"hidden_series": list(sets.get("hidden_series") or []), "chart_opacity_pct": 100 if opacity is None else opacity}


def _card_style(conf, key):
    """The card's own look when its Settings say so (logic.stat_cards: use_custom_style, Dashboard_* keys)."""
    try:
        from ..details.logic.stat_cards import get_dashboard_local_stat_style, merge_stat_card_style_config
        from .theme import stat_style

        local = get_dashboard_local_stat_style(conf, key)
        if not local.get("use_custom_style"):
            return None
        return stat_style(merge_stat_card_style_config(conf, local))
    except Exception:
        return None


def _twin_of(key):
    """{"active": bool} for the cards with an "Active days only" twin (Reviews/Day, Time/Day), else None."""
    from ..details.logic.stat_cards import active_day_twin

    twin = active_day_twin(key)
    return {"active": twin[1]} if twin else None


def stats(deck, span, options=None):
    """The stat cards of the Deep Dive row: label, shown value and color of each, in the
    configured order. Values come from the same builder as the pinned stat cards."""
    from ..const.config import Config
    from ..details.ui import STAT_KEY_TO_COLOR_KEY
    from ..details.widgets.pinned.widget_factory.builders.stat_card import _build_stat_values_map
    from ..details.widgets.stats_cards import get_stat_card_info
    from ..const.theme.color_resolver import get_color
    from ..i18n import tr_name

    cfg = _cfg()
    conf = cfg.config
    values = _build_stat_values_map(
        deck, int(span), _custom_days(), cfg=cfg, with_day_stats=True, with_deck_state=True,
    ) or {}
    labels = conf.get(Config.DASH_STAT_LABELS) or {}
    colors = conf.get(Config.DASH_STAT_COLORS) or {}
    cards = []
    rows = conf.get(Config.DASH_STAT_ROW_NUMS) or {}
    for key in conf.get(Config.DASH_STAT_ORDER) or []:
        if not conf.get(key, False):
            continue
        title, fallback = get_stat_card_info(key)
        color_key = STAT_KEY_TO_COLOR_KEY.get(key)
        color = colors.get(key) or (get_color(conf, color_key, "details") if color_key else fallback)
        label = labels.get(key)
        cards.append({
            "key": key,
            "label": title if label is None else tr_name(str(label)),
            "value": str(values.get(key, "...")),
            "color": color,
            "row": int(rows.get(key, 0) or 0),
            "own_color": bool(colors.get(key)),
            "style": _card_style(conf, key),
            "active_twin": _twin_of(key),
        })
    return {"cards": cards,
            "unlocked": list(conf.get("UNLOCKED_EFFECTS") or []),
            "hover_effect": bool(conf.get(Config.DASHBOARD_HOVER_EFFECT, True))}


def _plain(v):
    """JSON-safe copy of a chart payload (tuples and sets to lists, keys to text, NaN to null)."""
    if isinstance(v, dict):
        return {str(k): _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set, frozenset)):
        return [_plain(x) for x in v]
    if isinstance(v, float):
        return None if v != v or v in (float("inf"), float("-inf")) else v
    if v is None or isinstance(v, (bool, int, str)):
        return v
    return str(v)


_LIVE = {"cfg": None, "own": None}  # the window's config while the settings dialog is open (its live preview, before Save)


def _preview_sets(chart_type):
    """A Deep Dive chart's settings dialog showing its changes live (live_preview.py): what it has so far (its
    Chart Appearance: opacity, average / total lines, gradient, grid...), over the saved settings, until it closes."""
    own = _LIVE.get("own") or {}
    return own.get(chart_type) or {}


def _cfg():
    from ..config import addon_config as _addon_config

    return _LIVE["cfg"] or _addon_config()


# a pinned widget's own settings while its data is read (fetch(own=...)): its header controls (Future Due's breakdown,
# backlog, range; the FSRS charts' filters) are saved on the widget, read here before Deep Dive's (one per thread:
# the pinned charts are read in the background)
import threading as _threading

_OWN = _threading.local()


def _custom_days(options=None):
    own = getattr(_OWN, "d", None)
    d = (own or {}).get("custom_days") if isinstance(own, dict) else None
    if d is None and isinstance(options, dict):
        d = options.get("custom_days")
    try:
        return int(d) if d else 7
    except (TypeError, ValueError):
        return 7


def _setting(chart, key, default=None):
    from ..const.config import Config

    own = getattr(_OWN, "d", None)
    if own is not None and key in own:
        return own.get(key, default)
    sets = (_cfg().config.get(Config.DEEP_DIVE_WIDGET_SETTINGS) or {}).get(chart + "_g") or {}
    return sets.get(key, default)


def distribution(deck, span, options=None):
    from ..details.widgets.pinned.widget_factory.shared.reviews import load_distribution_source

    src = load_distribution_source(deck, span, cache=None, cfg=_cfg(), custom_days=_custom_days(options), fail_if_not_cached=False)
    return {"data": _plain(src.get("distribution_data"))}


def hourly(deck, span, options=None):
    from ..details.logic.metrics import HourlyDataProvider

    f = bool(_setting("hourly", "include_filtered", True))  # the reviews of filtered decks (revlog type 3)
    return {"data": _plain(HourlyDataProvider.fetch_data(_cfg(), deck, deck == -1, span, custom_days=_custom_days(options), filtered=f)),
            "include_filtered": f}


def review_intervals(deck, span, options=None):
    from ..details.logic.metrics import ReviewIntervalsDataProvider
    from ..details.widgets.common.fsrs_filters import (
        compute_fsrs_distribution_percentiles,
        resolve_fsrs_filter_choice,
        resolve_fsrs_filter_max_days,
        resolve_fsrs_filters,
    )

    from .extras_providers import pie_settings

    susp = bool(_setting("review_intervals", "include_suspended", True))  # Include Suspended
    data = ReviewIntervalsDataProvider.fetch_data(_cfg(), deck, deck == -1, span, suspended=susp) or {}
    modes, short, _long = resolve_fsrs_filters(_setting("review_intervals", "filter_modes", None))
    idx, mode = resolve_fsrs_filter_choice(_setting("review_intervals", "time_span_idx"), modes=modes)
    dist = data.get("distribution", {}) or {}
    found = compute_fsrs_distribution_percentiles(dist, percentiles=(0.50, 0.95), positive_only=True, default_value=30)
    p50 = int(found["values"].get(0.50, data.get("p50", 31)))
    p95 = int(found["values"].get(0.95, data.get("p95", 365)))
    max_days = resolve_fsrs_filter_max_days(
        mode, dist=dist, p50=p50, p95=p95, one_month_days=31, all_fallback_days=30, invalid_fallback_days=31, minimum_days=1
    )
    filtered = {k: v for k, v in dist.items() if 0 < k <= max_days}
    label = short[modes.index(mode)] if mode in modes else ""
    return {
        "data": _plain(data),
        "include_suspended": susp,
        "max_days": max_days,
        "median": p50 if found["total"] > 0 else 0,
        "filter_label": str(label),
        "filter_labels": [str(x) for x in _long],
        "filter_idx": idx,
        "shown_total": sum(filtered.values()),
        **pie_settings("review_intervals"),  # the pie view's slices
    }


def future_due(deck, span, options=None):
    from ..details.logic.metrics import FutureDueDataProvider
    from ..details.logic.metrics.future_due import resolve_breakdown
    from ..details.widgets.common import resolve_future_due_ranges

    from ..details.widgets.common import resolve_future_due_choice

    ranges, _short, _long = resolve_future_due_ranges(_setting("future_due", "radio_ranges", None))
    idx, rng, _src = resolve_future_due_choice(
        _setting("future_due", "time_span_idx", None), fallback_range=span, default_idx=0, ranges=ranges)
    backlog = bool(_setting("future_due", "show_backlog", False))
    bd = resolve_breakdown(_setting("future_due", "breakdown"), _setting("future_due", "show_breakdown", False))
    data = FutureDueDataProvider.fetch_data(_cfg(), deck, deck == -1, rng, include_backlog=backlog, breakdown=bd,
                                           hidden_parts=_setting("future_due", "hidden_series", None) or ())
    label = _short[idx] if 0 <= idx < len(_short) else ""
    return {"data": _plain(data), "range": _plain(rng), "range_label": str(label), "range_labels": [str(x) for x in _long], "range_idx": idx, "backlog": backlog, "breakdown": _plain(bd)}


def added(deck, span, options=None):
    from ..details.widgets.pinned.widget_factory.shared.reviews import load_added_source

    src = load_added_source(deck, span, cache=None, cfg=_cfg(), custom_days=_custom_days(options), fail_if_not_cached=False)
    return {"rows": _plain(src.get("oldest_first"))}


def card_counts(deck, span, options=None):
    from ..details.logic.data.section_fetchers import fetch_section_data

    from ..const.config import Config

    conf = _cfg().config
    raw_counts = _plain(fetch_section_data(_cfg(), "card_counts", deck_id=deck, is_deleted=deck == -1))
    merged = raw_counts.pop("merged", None) if isinstance(raw_counts, dict) else None
    out = {
        "counts": raw_counts,
        "separate": bool(conf.get(Config.PIE_CHART_SEPARATE_SUSPENDED, False)),
        "show_legend": bool(_setting("card_counts", "show_legend", True)),
        "legend_mode": str(_setting("card_counts", "legend_mode", "auto") or "auto"),
        "legend_pct": bool(_setting("card_counts", "legend_pct", False)),  # each count's share in the legend
        "bars_view": bool(_setting("card_counts", "bars_view", False)),  # Bars: the counts as bars (pie.js)
        # the card types hidden from a click on the legend (pie.js toggleKind)
        "hidden_kinds": [str(k) for k in (_setting("card_counts", "hidden_kinds", None) or []) if k],
    }
    if merged:
        out["merged"] = merged
    return _counts_at(out, deck, options)


def _counts_at(out, deck, options):
    """Card Counts at a date: the day picked in its header (options
    "at"), from the first review to today. A past day's counts are the cards' states at its end (card_states.timeline:
    suspended and buried are not in the history, a card counts in its scheduling state)."""
    if deck == -1:
        return out  # deleted cards: no history of their states
    from datetime import date

    from ..const.base import Period
    from .extras_providers import machine_days

    try:
        day, first, today, _ = machine_days(Period.TOTAL, {"at": (options or {}).get("at")})
        if day < today:
            from ..details.logic.metrics.card_states import KEYS, timeline
            c = [int(v) for v in timeline(_cfg(), deck, False).at(day)]
            counts = {k: 0 for k in (out.get("counts") or {})}
            counts.update(zip(KEYS, c))
            if "total" in counts:
                counts["total"] = sum(c)
            out["counts"] = counts
            out.pop("merged", None)
    except Exception as e:
        from ..details.logic.logger import log_warn

        log_warn(f"card counts at a date: {e!r}", tag="WEB")
        return out
    out.update(date=date.fromordinal(day).isoformat(), first=date.fromordinal(first).isoformat(),
               today=date.fromordinal(today).isoformat(), past=day < today,
               day_slider=bool(_setting("card_counts", "day_slider", False)))
    return out


def _fsrs(deck, key):
    from ..details.widgets.pinned.widget_factory.builders.fsrs_common import fetch_fsrs_data

    if deck == -1:  # deleted cards: no FSRS state
        return {"data": {}}
    return {"data": _plain((fetch_fsrs_data(deck, _cfg()) or {}).get(key, {}))}


def stability(deck, span, options=None):
    from ..details.widgets.common.fsrs_filters import (
        compute_fsrs_distribution_percentiles,
        resolve_fsrs_filter_choice,
        resolve_fsrs_filter_max_days,
        resolve_fsrs_filters,
    )
    from ..details.widgets.pinned.widget_factory.builders.fsrs_common import fetch_fsrs_data
    from .extras_providers import pie_settings

    dist = ({} if deck == -1 else (fetch_fsrs_data(deck, _cfg()) or {}).get("stability", {})) or {}
    modes, short, _long = resolve_fsrs_filters(_setting("stability", "filter_modes", None))
    idx, mode = resolve_fsrs_filter_choice(_setting("stability", "time_span_idx"), modes=modes)
    found = compute_fsrs_distribution_percentiles(dist, percentiles=(0.50, 0.95), positive_only=False, default_value=30)
    p50 = int(found["values"].get(0.50, 30))
    p95 = int(found["values"].get(0.95, 30))
    max_days = resolve_fsrs_filter_max_days(
        mode, dist=dist, p50=p50, p95=p95, one_month_days=31, all_fallback_days=30, invalid_fallback_days=1,
        minimum_days=1, positive_only=False,
    )
    median = int(compute_fsrs_distribution_percentiles(dist, percentiles=(0.50,), positive_only=False, default_value=0)["values"].get(0.50, 0))
    label = short[modes.index(mode)] if mode in modes else ""
    return {"data": _plain(dist), "max_days": max_days, "median": median, "filter_label": str(label),
            "filter_labels": [str(x) for x in _long], "filter_idx": idx, **pie_settings("stability")}


def _fsrs_split(deck, key):
    """Difficulty / Retrievability, with each card type's bars when its Breakdown by Type is on (off by default)."""
    if deck == -1 or not _setting(key, "breakdown", False):
        out = _fsrs(deck, key)
        out["breakdown"] = False
        return out
    from ..details.logic.history_provider import HistoryProvider

    stats = HistoryProvider.fetch_fsrs_stats(_cfg(), deck) or {}
    parts = stats.get("by_kind") or {}
    return {"data": _plain(stats.get(key, {})), "breakdown": True,
            "by_kind": {k: _plain((parts.get(k) or {}).get(key, {})) for k in ("learn", "young", "mature")}}


def difficulty(deck, span, options=None):
    return _fsrs_split(deck, "difficulty")


def retrievability(deck, span, options=None):
    return _fsrs_split(deck, "retrievability")


def retention(deck, span, options=None):
    from ..details.widgets.pinned.widget_factory.shared.reviews import load_retention_source

    src = load_retention_source(deck, span, cache=None, cfg=_cfg(), custom_days=_custom_days(options), fail_if_not_cached=False)
    return {"data": _plain(src.get("retention_data"))}


_FUTURE = {}


def _deck_key(deck):
    return tuple(deck) if isinstance(deck, list) else deck


def _search_key():
    try:
        from ..details.logic.search_filter import active_search_query

        return active_search_query() or ""
    except Exception:
        return ""


def _future_cells(deck, year):
    """Cards due per day of a year (the heatmap's future days), kept a minute: a zoom asks for them on every step."""
    import time

    from ..details.logic.history_provider import HistoryProvider

    key = (_deck_key(deck), year, _search_key())
    hit = _FUTURE.get(key)
    if hit and time.monotonic() - hit[0] < 60:
        return hit[1]
    cells = HistoryProvider.fetch_future_reviews(deck, year, _cfg())
    if len(_FUTURE) > 16:
        _FUTURE.clear()
    _FUTURE[key] = (time.monotonic(), cells)
    return cells


def heatmap(deck, span, options=None):
    """Per-day entries of the heatmap (reviews, time, passed, card types), over the period shown."""
    from ..details.logic.data.transforms.heatmap_series import build_heatmap_data
    from ..details.widgets.pinned.widget_factory.shared.reviews import load_activity_source

    cdays = _custom_days(options)
    src = load_activity_source(deck, span, cache=None, cfg=_cfg(), custom_days=cdays, fail_if_not_cached=False,
                               allow_context_slow_ops=True)
    data, _ = build_heatmap_data(src.get("raw_hist") or [])
    # Cards due in the coming days (current and next year).
    try:
        from datetime import datetime

        from ..details.logic.data.transforms.heatmap_series import merge_heatmap_future_values

        year = datetime.now().year
        for y in (year, year + 1):
            cells = _future_cells(deck, y)
            if cells:
                merge_heatmap_future_values(data, cells, mode="max")
    except Exception as e:
        from ..details.logic.logger import log_warn

        log_warn(f"heatmap future: {e!r}", tag="WEB")
    # a new period: the heatmap goes to the period's last day (heatmap_anchor.range_last_day)
    anchor = None
    try:
        from ..details.logic.heatmap.range_anchor import range_last_day

        last = range_last_day(int(span), custom_days=cdays)
        if last is not None:
            anchor = {"first": None, "last": last.isoformat(), "full": True}
    except Exception:
        from ..details.logic.logger import log_swallowed

        log_swallowed()
    return {"data": _plain(data), "anchor": anchor}


def _history_slice(deck, span, first, last):
    """History rows (oldest first) between two day labels (pretty dates), or all of them (None, None)."""
    from ..details.widgets.pinned.widget_factory.shared.reviews import load_activity_source

    src = load_activity_source(deck, span, cache=None, cfg=_cfg(), custom_days=_custom_days(), fail_if_not_cached=False,
                               allow_context_slow_ops=True)
    raw = list(src.get("raw_hist") or [])
    raw.sort(key=lambda r: str(r.get("logical_date") or r.get("date") or ""))
    if first is None or last is None:
        return raw, raw
    labels = [str(r.get("pretty_date", "")) for r in raw]
    try:
        i0, i1 = labels.index(str(first)), labels.index(str(last))
    except ValueError:
        return raw, raw
    if i1 < i0:
        i0, i1 = i1, i0
    return raw[i0:i1 + 1], raw


_HIRES = {}


def _hires_rows(deck, bounds, kind="reviews"):
    """10-minute rows (oldest first) of [start_ms, end_ms), for the Activity chart zoomed in to a few days."""
    from ..details.logic.data.section_fetchers import fetch_section_data

    key = (_deck_key(deck), int(bounds[0]), int(bounds[1]), kind, _last_review_id(), _search_key())
    hit = _HIRES.get(key)
    if hit is None:
        hit = fetch_section_data(_cfg(), kind, deck_id=(None if deck == -1 else deck), is_deleted=(deck == -1),
                                 override_start_ms=int(bounds[0]), override_end_ms=int(bounds[1]), override_bin_ms=600000) or []
        if len(_HIRES) > 8:
            _HIRES.clear()
        _HIRES[key] = hit
    return hit


def _last_review_id():
    try:
        from aqt import mw

        return mw.col.db.scalar("SELECT max(id) FROM revlog") or 0
    except Exception:
        return 0


# the charts of answers by day that switch to 10-minute bins with Activity (as with the Today period)
AZ_METRICS = ("ratings", "forgotten", "review_speed", "introduced", "resets")


def adaptive(deck, span, first, last, source="activity", types=None):
    """Adaptive zoom: when the zoom shows 2 days or less,
    the charts of days switch to 10-minute bins over those days. {} when the window is wider (or already 10 minutes).
    types: the charts shown; those of AZ_METRICS among them (and the one zoomed) get their 10-minute rows too."""
    from ..utils import rollover_hour
    from ..details.widgets.charts.common.zoom import build_adaptive_fetch_bounds, resolve_adaptive_zoom_window

    if source == "added":
        from ..details.widgets.pinned.widget_factory.shared.reviews import load_added_source

        rows = list(load_added_source(deck, span, cache=None, cfg=_cfg(), custom_days=_custom_days(), fail_if_not_cached=False).get("oldest_first") or [])
        labels = [str(r.get("pretty_date", "")) for r in rows]
        try:
            i0, i1 = sorted((labels.index(str(first)), labels.index(str(last))))
        except ValueError:
            return {}
        sl = rows[i0:i1 + 1]
    else:
        sl, full = _history_slice(deck, span, first, last)
        if sl is full:
            return {}
    win = resolve_adaptive_zoom_window(sl, date_keys=("logical_date", "date"))
    if not win:
        return {}
    bounds = build_adaptive_fetch_bounds(win["first_dt"], win["last_dt"], offset_seconds=rollover_hour() * 3600)
    hist = _hires_rows(deck, bounds, "reviews")
    added_rows = _hires_rows(deck, bounds, "added")
    has_reviews = any((r.get("reviews") or 0) > 0 for r in hist)
    out = {"bounds": list(bounds), "added": {"rows": _plain(added_rows)}}
    if not has_reviews and source == "added":
        out["added_only"] = True
        return out
    if not hist:
        return {}
    from ..details.logic.data.transforms.activity_series import (
        attach_breakdown_totals, build_breakdown_rows, filter_activity_types)
    from ..details.logic.data.transforms.retention_series import RETENTION_SERIES_KEYS, build_retention_series

    shown = filter_activity_types(hist, _setting("activity", "hidden_review_types", None))
    out["activity"] = {"rows": _daily_rows(attach_breakdown_totals(build_breakdown_rows(shown, count_key_style="plain"), shown), shown)}
    # the start of each 10-minute row (ms), for the one-dot-per-review view
    from datetime import datetime

    def _ms(r):
        try:
            return int(datetime.strptime(str(r.get("date")), "%Y-%m-%d %H:%M").timestamp() * 1000)
        except Exception:
            return None
    out["times"] = [_ms(r) for r in hist]
    out["retention"] = {"data": _plain(build_retention_series(hist, strict_series=RETENTION_SERIES_KEYS))}
    from .extras_providers import daily_metric

    for t in AZ_METRICS:
        if t != source and t not in (types or ()):
            continue
        try:
            out[t] = daily_metric(t, deck, span, days=hist)
        except Exception as e:
            from ..details.logic.logger import log_warn

            log_warn(f"adaptive {t}: {e!r}")
    return out


def _buttons_hours(rows):
    """Answer Buttons and Hourly summed over history rows (zoom_stats, zoom_follower)."""
    dist = {"learning": [0, 0, 0, 0], "young": [0, 0, 0, 0], "mature": [0, 0, 0, 0]}
    hourly_d = {h: {"total": 0, "correct": 0} for h in range(24)}
    for r in rows:
        for k, key in (("learning", "learning_buttons"), ("young", "young_buttons"), ("mature", "mature_buttons")):
            v = r.get(key) or []
            if len(v) == 4:
                for i in range(4):
                    dist[k][i] += v[i]
        hb = r.get("hourly")
        if hb:
            for h in range(24):
                if h in hb:
                    hourly_d[h]["total"] += hb[h].get("total", 0)
                    hourly_d[h]["correct"] += hb[h].get("correct", 0)
    return dist, hourly_d


# the charts with no time axis that follow a zoom of a chart of days (zoom_stats; the heatmap aside)
ZOOM_FOLLOWERS = ("distribution", "hourly", "answer_time", "interval_ratings", "rating_fatigue", "sibling_ratings",
                  "fsrs_calibration", "forgetting_curve", "fsrs_fatigue", "week_hours", "todays_retention")


def _day_of(r):
    return str(r.get("logical_date") or r.get("date") or "")[:10]


def _hourly_for_zoom(deck, span, rows, bounds=None):
    """Hourly breakdown over a zoomed slice: respects include_filtered and works on 10-minute bounds."""
    f = bool(_setting("hourly", "include_filtered", True))
    if not bounds and f:
        _dist, hourly_d = _buttons_hours(rows)
        return {"data": _plain(hourly_d), "include_filtered": f}
    from ..details.logic.metrics import HourlyDataProvider

    if bounds:
        s_ms, e_ms = int(bounds[0]), int(bounds[1])
        if rows:
            from datetime import datetime

            try:
                t0 = int(datetime.strptime(str(rows[0].get("date") or "")[:16], "%Y-%m-%d %H:%M").timestamp() * 1000)
                t1 = int(datetime.strptime(str(rows[-1].get("date") or "")[:16], "%Y-%m-%d %H:%M").timestamp() * 1000) + 600000
                s_ms, e_ms = max(s_ms, t0), min(e_ms, t1)
            except Exception:
                pass
    else:
        from datetime import datetime, timedelta

        from ..utils import rollover_hour

        ds = sorted({d for d in (_day_of(r) for r in rows) if len(d) == 10})
        if not ds:
            return {"data": _plain({h: {"total": 0, "correct": 0} for h in range(24)}), "include_filtered": f}
        roll = int(rollover_hour() or 0)
        d0 = datetime.strptime(ds[0], "%Y-%m-%d").replace(hour=roll)
        d1 = datetime.strptime(ds[-1], "%Y-%m-%d").replace(hour=roll) + timedelta(days=1)
        s_ms, e_ms = int(d0.timestamp() * 1000), int(d1.timestamp() * 1000)
    hourly_d = HourlyDataProvider.fetch_data(_cfg(), deck, deck == -1, span, override_start_ms=s_ms, override_end_ms=e_ms, filtered=f)
    return {"data": _plain(hourly_d), "include_filtered": f}


def zoom_follower(chart_type, deck, span, days, options=None, own=None):
    """One chart of ZOOM_FOLLOWERS over the zoomed days (days: first and last, ISO) that fall in its own period,
    read with a pinned widget's own settings (own, as fetch): zoom_stats for one chart, for the main screen. None
    when those days are its whole period, or none of it (it shows its own data)."""
    if chart_type not in ZOOM_FOLLOWERS or not days:
        return None
    _OWN.d = own
    try:
        _rows, full = _history_slice(deck, span, None, None)
        rows = [r for r in full if days[0] <= _day_of(r) <= days[1]]
        if not rows or len(rows) == len(full):
            return None
        first, last = rows[0].get("pretty_date"), rows[-1].get("pretty_date")
        if chart_type == "distribution":
            dist, _hourly_d = _buttons_hours(rows)
            return {"data": _plain(dist)}
        if chart_type == "hourly":
            return _hourly_for_zoom(deck, span, rows)
        from .extras_providers import daily_metric, todays_retention, week_hours

        opts = dict(options or {}, _zoom=(first, last))
        if chart_type == "week_hours":
            return week_hours(deck, span, opts)
        if chart_type == "todays_retention":
            return todays_retention(deck, span, opts)
        return daily_metric(chart_type, deck, span, opts)
    except Exception as e:
        from ..details.logic.logger import log_warn

        log_warn(f"zoom follower {chart_type}: {e!r}", tag="WEB")
        return None
    finally:
        _OWN.d = None


def zoom_stats(deck, span, first=None, last=None, bounds=None, types=None):
    """What follows a zoom of Activity: the stat cards, Answer Buttons, Hourly and the Heatmap over the same days
    (the same sums as the native _update_stats_from_history). types: optional list of requested keys to compute."""
    from ..const.config import Config
    from ..details.logic.data.transforms.heatmap_series import build_heatmap_data, merge_heatmap_future_values
    from ..details.logic.stat_cards import (
        STAT_VALUE_FIELD_BINDINGS, build_dashboard_history_totals, build_dashboard_stat_values)

    want = set(types) if types is not None else None
    if bounds:  # zoomed inside the 10-minute view: the sums of those 10-minute rows
        full = _hires_rows(deck, bounds, "reviews")
        labels = [str(r.get("pretty_date", "")) for r in full]
        rows = full
        if first is not None and last is not None and str(first) in labels and str(last) in labels:
            i0, i1 = sorted((labels.index(str(first)), labels.index(str(last))))
            rows = full[i0:i1 + 1]
        full = None  # always "zoomed": the window is a part of the period
    else:
        rows, full = _history_slice(deck, span, first, last)
    out = {}
    zoomed = rows is not full
    if want is None or "stats" in want:
        base = stats(deck, span)
        if zoomed and rows:
            prec = _cfg().config.get(Config.STATS_PRECISION, 2)
            vals = build_dashboard_stat_values(build_dashboard_history_totals(rows, streak_current=0),
                                               use_decimal=True, hrs_unit="h", min_unit=" min", prec=prec)
            history_fields = {"total_time", "reviews", "avg_time", "ret_all", "ret_young", "ret_mat", "active_days", "days_learned",
                              "longest_streak", "reviews_per_day", "time_per_day", "reviews_per_active_day", "time_per_active_day",
                              "ret_true", "rev_young", "rev_mature", "again",
                              "best_day", "lapses"}
            by_key = {dash: vals.get(field) for field, _dd, dash in STAT_VALUE_FIELD_BINDINGS if field in history_fields}
            for c in base["cards"]:
                if by_key.get(c["key"]) is not None:
                    c["value"] = str(by_key[c["key"]])
        out["stats"] = base
    if not zoomed:
        return out
    if want is None or "distribution" in want or "hourly" in want:
        if want is None or "distribution" in want:
            dist, _hourly_d = _buttons_hours(rows)
            out["distribution"] = {"data": _plain(dist)}
        if want is None or "hourly" in want:
            out["hourly"] = _hourly_for_zoom(deck, span, rows, bounds=bounds)
    # the charts of the period with no time axis follow the zoomed days too (Answer Time, Rating by Interval)
    try:
        from .extras_providers import daily_metric

        for wt in ("answer_time", "interval_ratings", "rating_fatigue", "sibling_ratings", "fsrs_calibration", "forgetting_curve", "fsrs_fatigue"):
            if want is None or wt in want:
                if bounds:
                    out[wt] = daily_metric(wt, deck, span, days=rows)
                else:
                    out[wt] = daily_metric(wt, deck, span, {"_zoom": (first, last)})
        need_wh = want is None or "week_hours" in want
        need_tr = want is None or "todays_retention" in want
        if need_wh or need_tr:
            from .extras_providers import todays_retention, week_hours

            # Week by Hour and First Answer Retention: inside the 10-minute view, the whole days shown
            if bounds:
                ds = sorted({str(r.get("logical_date") or "")[:10] for r in rows if r.get("logical_date")})
                if ds:
                    if need_wh:
                        out["week_hours"] = week_hours(deck, span, {"_dates": (ds[0], ds[-1])})
                    if need_tr:
                        out["todays_retention"] = todays_retention(deck, span, {"_dates": (ds[0], ds[-1])})
            else:
                if need_wh:
                    out["week_hours"] = week_hours(deck, span, {"_zoom": (first, last)})
                if need_tr:
                    out["todays_retention"] = todays_retention(deck, span, {"_zoom": (first, last)})
    except Exception as e:
        from ..details.logic.logger import log_warn

        log_warn(f"zoom followers: {e!r}", tag="WEB")
    if want is None or "heatmap" in want:
        try:
            data, _ = build_heatmap_data(rows)
            from datetime import datetime

            year = datetime.now().year
            for y in (year, year + 1):
                cells = _future_cells(deck, y)
                if cells:
                    merge_heatmap_future_values(data, cells, mode="max")
            # the heatmap goes to the zoomed days (stats_parts.runtime_updates: zoom_year_anchor, continuous offset)
            ds = [str(r.get("logical_date") or "")[:10] for r in rows if r.get("logical_date")]
            anchor = {"first": min(ds), "last": max(ds), "full": False} if ds else None
            try:  # a zoom reaching the newest day counts as the whole period (anchored on the period's last day)
                if anchor and full:
                    newest = max(str(r.get("logical_date") or "")[:10] for r in full)
                    if anchor["last"] >= newest:
                        from ..details.logic.heatmap.range_anchor import range_last_day

                        rl = range_last_day(int(span), custom_days=_custom_days())
                        if rl is not None:
                            anchor = {"first": anchor["first"], "last": rl.isoformat(), "full": True}
            except Exception:
                from ..details.logic.logger import log_swallowed

                log_swallowed()
            out["heatmap"] = {"data": _plain(data), "anchor": anchor}
        except Exception as e:
            from ..details.logic.logger import log_warn

            log_warn(f"zoom heatmap: {e!r}", tag="WEB")
    return out


PROVIDERS = {
    "activity": activity, "distribution": distribution, "hourly": hourly, "review_intervals": review_intervals,
    "future_due": future_due, "added": added, "card_counts": card_counts, "stability": stability,
    "difficulty": difficulty, "retrievability": retrievability, "retention": retention, "heatmap": heatmap,
}


def is_empty(chart_type, payload, deck=None, even_shown=False):
    """True when the Deep Dive leaves this chart out (no data and Config.SHOW_EMPTY_CHARTS off).
    even_shown: whatever that setting (the gallery's pictures)."""
    from ..const.config import Config

    try:
        shown = bool(_cfg().config.get(Config.SHOW_EMPTY_CHARTS, False)) and not even_shown
        if shown or not isinstance(payload, dict) or payload.get("error") or payload.get("fsrs_unsupported"):
            return False
        d = payload.get("data")
        if chart_type == "added":
            return not any((r or {}).get("count", 0) > 0 for r in (payload.get("rows") or []))
        if chart_type == "distribution":
            from ..details.logic.data.section_fallbacks import has_distribution_values

            return not has_distribution_values(d or {})
        if chart_type == "hourly":
            return not d or all((v or {}).get("total", 0) == 0 for v in d.values())
        if chart_type == "future_due":
            d = d or {}
            return not (d.get("total", 0) > 0 or (payload.get("backlog") and d.get("backlog", 0) > 0))
        if chart_type == "review_intervals":
            return (d or {}).get("total", 0) <= 0
        if chart_type in ("stability", "difficulty", "retrievability", "stability_history", "difficulty_history"):
            return not d
        if chart_type == "heatmap":
            return not d
        try:
            from ..details.ui.deep_dive.extra_charts import BY_TYPE as _EXTRA

            kind = _EXTRA[chart_type].kind if chart_type in _EXTRA else None
        except Exception:
            kind = None
        if kind is not None:
            # extra_charts._has_data: totals for the interval / card / today charts, else any day with reviews
            if kind in ("intervals", "cards"):
                return ((d or {}).get("total", 0) or 0) <= 0
            if kind == "today":
                return (payload.get("total", 0) or 0) <= 0
            if kind == "sxr":  # SxR Heatmap: no review card with a memory state
                return not payload.get("points")
            if kind == "bw":  # B-W Matrix: no answer with a memory state before it
                return not payload.get("cells")
            if kind == "custom":  # Custom Pie: always shown (its searches are edited from it)
                return False
            if kind == "curve":  # the first forgetting curves: no sample for any rating
                return not any((s or {}).get("n") for s in (payload.get("series") or []))
            if "counts" in payload:
                return not any(v for v in (payload.get("counts") or {}).values())
            return not any(
                ((r or {}).get("reviews", 0) or (r or {}).get("_reviews", 0) or (r or {}).get("seconds", 0)) > 0
                for r in (payload.get("rows") or [])
            )
        if chart_type == "card_counts":
            c = payload.get("counts") or {}
            return deck == -1 or (c.get("total", 0) or sum(v for v in c.values() if isinstance(v, (int, float)))) <= 0
    except Exception:
        return False
    return False


TEXT_PREFIX = "text:"


def is_text(chart_type):
    """A text of the Deep Dive ("text:1", "text:2"...), not a chart."""
    return isinstance(chart_type, str) and chart_type.startswith(TEXT_PREFIX)


def text_widgets(conf=None):
    """The Deep Dive's texts: {id: {"template": ...}} (Config.DEEP_DIVE_TEXT_WIDGETS)."""
    from ..const.config import Config

    conf = _cfg().config if conf is None else conf
    raw = conf.get(Config.DEEP_DIVE_TEXT_WIDGETS) or {}
    return {k: v for k, v in raw.items() if is_text(k) and isinstance(v, dict)} if isinstance(raw, dict) else {}


def text_data(wid, deck, span):
    """A text's sentence for the deck and period shown: the pinned text widget's variables ({reviews}, {retention},
    {reviews:week}, {reviews@Deck}...), a variable without its own deck or period taking the window's."""
    from ..details.widgets.pinned.widget_factory.builders.text_label import _build_runtime_payload, safe_html, shown_template

    t = text_widgets().get(wid)
    template = shown_template((t or {}).get("template") or "")
    if not template.strip():
        return {"html": "", "blank": True}
    try:
        span = int(span)
    except (TypeError, ValueError):
        span = -1
    payload = _build_runtime_payload(template, deck, span, _custom_days(), cfg=_cfg())
    return {"html": safe_html((payload or {}).get("resolved") or ""), "blank": False}


def fetch(chart_type, deck, span, options=None, own=None):
    if is_text(chart_type):
        try:
            return text_data(chart_type, deck, span)
        except Exception as e:
            from ..details.logic.logger import log_warn

            log_warn(f"provider {chart_type}: {e!r}", tag="WEB")
            return {"error": repr(e)}
    fn = PROVIDERS.get(chart_type)
    if not fn:
        return {}
    from ..details.logic.fsrs_math import CURVE_CHARTS, curve_known

    if chart_type in CURVE_CHARTS and not curve_known():
        # these charts work out a recall with the formulas of the FSRS versions known here: a note instead
        return {"fsrs_unsupported": True}
    _OWN.d = own
    try:
        out = fn(deck, span, options)
        if isinstance(out, dict) and is_empty(chart_type, out, deck):
            out = dict(out, _empty=True)
        return out
    except Exception as e:  # one chart failing must not blank the others
        from ..details.logic.logger import log_warn

        log_warn(f"provider {chart_type}: {e!r}", tag="WEB")
        return {"error": repr(e)}
    finally:
        _OWN.d = None


def default_widgets():
    """The charts of the window, in the configured order (hidden ones removed, extra ones added)."""
    from ..const.config import Config

    conf = _cfg().config
    hidden = set(conf.get(Config.DEEP_DIVE_HIDDEN_CHARTS) or [])
    texts = text_widgets(conf)  # a text removed leaves the order (its place in it is only kept while it exists)
    from ..details.widgets.charts.more_charts import BY_TYPE as _EXTRA

    extras = [t.get("type") if isinstance(t, dict) else t for t in conf.get(Config.DEEP_DIVE_EXTRA_CHARTS) or []]
    # an added chart only while it is added (the order keeps the types once placed: one taken off came back)
    order = [t for t in (conf.get(Config.DEEP_DIVE_CHART_ORDER) or [])
             if t not in hidden and (not is_text(t) or t in texts) and (t not in _EXTRA or t in extras)]
    for key in extras:
        if key and key not in order:
            order.append(key)
    order += [t for t in texts if t not in order]
    return [{"id": t, "type": t, "options": {} if is_text(t) else widget_options(t)} for t in order]


# ---- deck table (the drawer under the cards) ------------------------------------------------
def _deck_figures(did, span, need_hist, need_state):
    """A deck's figures from the history cache for the new table columns: its days over the span (period length,
    studied days, best day) and its current state (cards, due cards, FSRS averages). Kept until a new review."""
    from ..const import Period
    from ..details.logic.history_cache import GlobalHistoryCache
    from ..details.logic.stat_cards import CARD_STATE_FIELDS, history_day_stats

    span = span or {}
    rng = span.get("range", "week")
    kw = dict(custom_days=span.get("days", 7), custom_type=span.get("custom_type", "relative"),
              start_date_str=span.get("start_date", ""), end_date_str=span.get("end_date", ""))

    def compute():
        out = {}
        if need_hist:
            try:
                ctx = GlobalHistoryCache.get_context(did, rng, allow_sync_check=False, **kw) or {}
                ds = history_day_stats(ctx.get("reviews") or [])
            except Exception:
                ds = {}
            days = ds.get("days_in_period") or 0
            out["_days"] = days
            out["_active"] = ds.get("active_days", 0) if days else 0
            out["best_day"] = ds.get("best_day") if days else None
            out["days_learned"] = (ds.get("active_days", 0) / days * 100) if days else None
        if need_state:
            try:
                tot = GlobalHistoryCache.get_context(did, Period.TOTAL, allow_sync_check=False) or {}
            except Exception:
                tot = {}
            counts = tot.get("counts")
            for field, keys in CARD_STATE_FIELDS.items():
                out[field] = sum(counts.get(k, 0) or 0 for k in keys) if isinstance(counts, dict) else None
            fd = tot.get("future_due")
            dist = fd.get("distribution") if isinstance(fd, dict) else None
            out["due_today"] = out["backlog"] = None
            try:
                from aqt import mw

                today = int(mw.col.sched.today)
            except Exception:
                today = None
            if isinstance(dist, dict) and today is not None:
                due = back = 0
                for day, n in dist.items():
                    try:
                        day = int(day)
                    except (TypeError, ValueError):
                        continue
                    if 0 <= day < 1000000000:
                        if day == today:
                            due += n or 0
                        elif day < today:
                            back += n or 0
                out["due_today"], out["backlog"] = due, back
            fsrs = tot.get("fsrs") if isinstance(tot.get("fsrs"), dict) else {}
            for key, field in (("avg_retrievability", "retrievability"), ("avg_stability", "stability")):
                hist = fsrs.get(field) or {}
                n = sum(hist.values())
                if field == "retrievability":
                    # 1% bins 0..99 represent [i, i+1): use bin midpoint i+0.5 (100 stays 100)
                    out[key] = (sum((min(100.0, k + 0.5) if k < 100 else 100.0) * v for k, v in hist.items()) / n) if n > 0 else None
                else:
                    out[key] = (sum(k * v for k, v in hist.items()) / n) if n > 0 else None
        return out

    col_mod = 0
    if need_state:
        try:
            from aqt import mw

            col_mod = int(getattr(getattr(mw, "col", None), "mod", 0) or 0)
        except Exception:
            col_mod = 0
    key = ("deckfig", did, rng, repr(sorted(kw.items())), need_hist, need_state, col_mod)
    return dict(_memo(key, compute)[0])


_MEMO = {}


# the table's data is kept until a new review (the key carries the last review id) or this long: the normal window
# keeps each tab's snapshot for the session; 30 s made a tab seen a minute ago take its 300+ ms again
_KEEP_S = 1800.0


def _memo(key, fn, ttl=_KEEP_S):
    """The table's data per time span, kept for a while (the normal window keeps each tab's snapshot in memory):
    same key (and no new review in the history cache) = the same answer. Returns (value, hit)."""
    import time

    try:
        from ..details.logic.history_cache import GlobalHistoryCache

        rev = int(getattr(GlobalHistoryCache(), "last_max_rev_id", 0) or 0)
    except Exception:
        rev = 0
    try:
        from ..details.logic.search_filter import active_search_query
        sq = active_search_query()
    except Exception:
        sq = ""
    full = (key, rev, sq)
    now = time.monotonic()
    hit = _MEMO.get(full)
    if hit and now - hit[0] < ttl:
        return hit[1], True
    val = fn()
    if len(_MEMO) > 600:
        _MEMO.clear()
    _MEMO[full] = (now, val)
    return val, False


def table(tab, sort=None, expanded=None, deck=None, _prepared=None, _deck_rows=None):
    """Rows of the deck table for one time span, ready to show: ordered like the normal window
    (tree, sorted per column), every cell as text/HTML plus its sort value."""
    from ..const.config import Config
    from ..details.logic.data.core.forecast import forecast_days
    from ..details.logic.data.time_view.loader import load_stats_data
    from ..details.ui.table.core import get_dist_text, get_trend_html
    from ..details.ui.table.retention_visual import retention_visual_on
    from ..details.logic.formatting import fmt_num, stats_precision
    from ..config import addon_config as _addon_config
    from ..details.logic.tabs import get_active_tabs_config
    from ..i18n import num, tr, tr_n, tr_name
    from ..utils import format_hours

    if deck is not None:
        return _deck_table(deck, sort, expanded)
    cfg = _addon_config()
    conf = cfg.config
    tabs = get_active_tabs_config(cfg)
    tab = max(0, min(int(tab or 0), len(tabs) - 1))
    t = tabs[tab]
    range_type = t.get("range", "week")
    from ..details.logic.tabs.columns import COLUMNS as COL_ALL, FLAGS, GROUPS as COL_GROUPS, HISTORY_KEYS, LABELS, STATE_KEYS
    from ..details.logic.tabs.columns import DEFAULT_COLUMNS as COL_DEFAULTS, table_columns, table_show_counts

    # the columns: one list for every time span (Settings > Time Span, or the table header's right-click menu)
    shown = table_columns(conf)
    on = set(shown)
    show = {flag: k in on for k, flag in FLAGS.items()}
    show["show_counts"] = table_show_counts(conf)
    use_decimal, hrs_unit, min_unit = t.get("use_decimal", False), t.get("hrs_unit", "hrs"), t.get("min_unit", "min")
    show_trends = bool(conf.get(Config.SHOW_TRENDS, False))
    import time as _time

    from .trace import trace as _lw

    _t0 = _time.perf_counter()
    _hit = None
    if _prepared is not None:
        data = _prepared
    else:
        _args = dict(
            range_type=range_type, excluded_dids=conf.get(Config.EXCLUDED_DECKS, []),
            spark_precision=conf.get(Config.SPARKLINE_PRECISION, False), show_trends=show_trends,
            week_start=t.get("week_start", conf.get(Config.WEEK_START, 0)),
            custom_days=t.get("days", 7), custom_type=t.get("custom_type", "relative"),
            start_date_str=t.get("start_date", ""), end_date_str=t.get("end_date", ""),
        )
        data, _hit = _memo(("table", repr(sorted((k, repr(v)) for k, v in _args.items()))), lambda: load_stats_data(**_args))
    _t1 = _time.perf_counter()
    totals, tree = data["totals"], data["tree_data"]
    try:
        from ..details.ui import get_chart_color as gcc
        good, bad = gcc(Config.COLOR_GOOD), gcc(Config.COLOR_AGAIN)
        hard, easy = gcc(Config.COLOR_HARD), gcc(Config.COLOR_EASY)
    except Exception:
        good, bad, hard, easy = "#4CAF50", "#F44336", "#FF9800", "#2196F3"
    counts = show["show_counts"]
    deck_colors = conf.get(Config.DECK_COLORS, {}) or {}
    visual_buttons = bool(conf.get(Config.SHOW_BUTTONS_DIST_VISUAL, True))

    # order: the tree, each level sorted by the chosen column (the normal window's re-flatten)
    sort = sort or {}
    col = sort.get("col", "time")
    desc = bool(sort.get("desc", True))

    def val(d):
        r = d.get("reviews", 0)
        if col == "deck": return d.get("display_name", d.get("full_name", "")).lower()
        if col == "time": return d.get("time_ms", 0)
        if col == "reviews": return r
        if col == "retention": return (d.get("passed", 0) / r * 100) if r > 0 else -1
        if col == "ret_young": return (d.get("pass_young", 0) / d["rev_young"] * 100) if d.get("rev_young", 0) > 0 else -1
        if col == "ret_mature": return (d.get("pass_mat", 0) / d["rev_mat"] * 100) if d.get("rev_mat", 0) > 0 else -1
        if col == "avg_time": return (d.get("time_ms", 0) / r) if r > 0 else 0
        if col == "longest_streak": return d.get("streak_longest", 0)
        if col == "streak": return d.get("streak_current", 0)
        if col == "active_days": return d.get("active_days", 0)
        if col == "forecast":
            days = None if d.get("is_deleted") else forecast_days(d.get("new_limit", 0), d.get("max_days"), d.get("remaining_new", 0))
            return -1 if days is None else days
        if col in on:
            v = _extra_raw(d, False).get(col)
            return -1 if v is None else v
        return 0

    extra_on = on - set(FLAGS)
    need_hist, need_state = bool(extra_on & HISTORY_KEYS), bool(extra_on & STATE_KEYS)

    def _ctx_ref(d, total):
        """(deck id for the history cache, time span) of a row: the deck over the tab's span, or (View by Deck)
        the deck shown over the row's span."""
        if total:
            return None, t
        if "_span" in d:
            return d.get("_ctx_did"), d["_span"]
        return (-1 if d.get("is_deleted") else d.get("did")), t

    tot_hold = {}
    x_time = [0.0]

    def _extra_raw(d, total):
        """The new columns' numbers for a row (None: not available), kept on the row."""
        hold = tot_hold if total else d  # (not on totals: they are kept in the memo, with other columns)
        if "_x" in hold:
            return hold["_x"]
        src = totals if total else d
        g = lambda k: src.get(k, 0) or 0
        rev = totals["rev"] if total else g("reviews")
        time_h = totals["time"] if total else g("time_ms") / 3600000
        py, ry, pm, rm = g("pass_young"), g("rev_young"), g("pass_mat"), g("rev_mat")
        x = {"ret_true": ((py + pm) / (ry + rm) * 100) if (ry + rm) > 0 else None,
             "rev_young": ry, "rev_mature": rm, "again": g("again"), "lapses": (ry + rm) - (py + pm)}
        if need_hist or need_state:
            did, span = _ctx_ref(d, total)
            # Virtual folder rows have did=None without being collection total or View-by-Deck:
            # calling _deck_figures(None, ...) would fetch the entire collection's figures.
            is_virtual_folder = (not total) and ("_span" not in d) and (not d.get("is_deleted")) and (did is None)
            if not is_virtual_folder:
                _tx = _time.perf_counter()
                x.update(_deck_figures(did, span, need_hist, need_state))
                x_time[0] += _time.perf_counter() - _tx
                days, active = x.pop("_days", None), x.pop("_active", None)
                if need_hist:
                    x["reviews_per_day"] = (rev / days) if days else None
                    x["time_per_day"] = (time_h / days) if days else None
                    x["reviews_per_active_day"] = (rev / active) if active else None
                    x["time_per_active_day"] = (time_h / active) if active else None
        hold["_x"] = x
        return x

    tree = {k: dict(v) for k, v in tree.items()}
    kids = {}
    for path, info in tree.items():
        kids.setdefault(info.get("parent"), []).append(path)
    ordered = []

    def walk(parent, prefix):
        ch = sorted(kids.get(parent, ()), key=lambda p: val(tree[p]), reverse=desc)
        for i, p in enumerate(ch):
            last = i == len(ch) - 1
            tree[p]["tree_prefix"] = prefix + ("└── " if last else "├── ") if parent is not None else ""
            ordered.append(tree[p])
            walk(p, prefix + ("    " if last else "│   ") if parent is not None else "")

    walk(None, "")

    def days_text(n):
        return tr_n("{n} day", "{n} days", int(n))

    def trend(curr, prev, better=True, points=False):
        return get_trend_html(curr, prev, show_trends, better, color_good=good, color_bad=bad, points=points)

    def ret_cell(key, passed, rev, prev_pass, prev_rev):
        if rev and rev > 0 and retention_visual_on(key):
            pct = passed / rev * 100
            return {"bar": [max(rev - passed, 0), passed], "t": num("0%" if pct == 0 else f"{pct:.{stats_precision()}f}%"), "s": pct}
        if rev and rev > 0:
            ret = passed / rev * 100
            text = num("0%" if ret == 0 else f"{ret:.{stats_precision()}f}%")
            if counts:
                text += f" (<span style='color:{good}'>{fmt_num(passed)}</span>/<span style='color:{bad}'>{fmt_num(rev - passed)}</span>)"
            prev_ret = (prev_pass / prev_rev * 100) if (prev_rev or 0) > 0 else 0
            return {"t": text + trend(ret, prev_ret, points=True), "s": ret,
                    "tip": tr("Pass: {passed} / Fail: {failed}", passed=passed, failed=rev - passed)}
        return {"t": "N/A", "s": -1}

    def cells(d, total=False):
        c = {}
        if total:
            time_h, rev = totals["time"], totals["rev"]
            prev_time_h, prev_rev = totals["prev_time"], totals["prev_rev"]
        else:
            time_h, rev = d["time_ms"] / 3600000, d["reviews"]
            prev_time_h, prev_rev = d.get("prev_time_ms", 0) / 3600000, d.get("prev_reviews", 0)
        if show["show_time"]:
            c["time"] = {"t": format_hours(time_h, use_decimal=use_decimal, hrs_text=hrs_unit, min_text=min_unit) + trend(time_h, prev_time_h), "s": time_h}
        if show["show_reviews"]:
            c["reviews"] = {"t": fmt_num(rev) + trend(rev, prev_rev), "s": rev}
        if show["show_retention"]:
            c["retention"] = ret_cell("all", totals["pass"], totals["rev"], totals["prev_pass"], totals["prev_rev"]) if total else ret_cell("all", d["passed"], rev, d.get("prev_passed", 0), d.get("prev_reviews", 0))
        if show["show_retention_young"]:
            c["ret_young"] = ret_cell("young", totals["pass_young"], totals["rev_young"], totals["prev_pass_young"], totals["prev_rev_young"]) if total else ret_cell("young", d["pass_young"], d["rev_young"], d.get("prev_pass_young", 0), d.get("prev_rev_young", 0))
        if show["show_retention_mature"]:
            c["ret_mature"] = ret_cell("mature", totals["pass_mat"], totals["rev_mat"], totals["prev_pass_mat"], totals["prev_rev_mat"]) if total else ret_cell("mature", d["pass_mat"], d["rev_mat"], d.get("prev_pass_mat", 0), d.get("prev_rev_mat", 0))
        if show["show_buttons_dist"]:
            src = totals if total else d
            vals = [src["again"], src["hard"], src["good"], src["easy"]]
            tot = totals["rev"] if total else rev
            if visual_buttons:
                c["buttons"] = {"seg": vals, "t": "", "s": 0}
            else:
                cols = [bad, hard, good, easy]
                c["buttons"] = {"parts": [[get_dist_text(v, tot, counts), cols[i]] for i, v in enumerate(vals)], "t": "", "s": 0}
        if show["show_avg_time"]:
            if rev > 0:
                avg = time_h * 3600 / rev
                prev_avg = prev_time_h * 3600 / prev_rev if prev_rev > 0 else 0
                c["avg_time"] = {"t": tr("{value}s", value=num(f"{avg:.{stats_precision()}f}")) + trend(avg, prev_avg, False), "s": avg}
            else:
                c["avg_time"] = {"t": "N/A", "s": -1}
        src = totals if total else d
        ls, cs = src.get("streak_longest"), src.get("streak_current")
        if show["show_longest_streak"]:
            c["longest_streak"] = {"t": days_text(ls), "s": ls} if isinstance(ls, (int, float)) else {"t": "-", "s": -1}
        if show["show_streak"]:
            if isinstance(cs, (int, float)):
                c["streak"] = {"t": days_text(cs), "s": cs, "color": "#FFD700" if cs >= 365 else ("#52c41a" if cs >= 30 else None)}
            else:
                c["streak"] = {"t": "-", "s": -1}
        if show["show_active_days"]:
            ad = src.get("active_days", 0)
            c["active_days"] = {"t": fmt_num(ad), "s": ad}
        if show["show_forecast"]:
            if total:
                rem = totals["remaining"]
                days = forecast_days(totals.get("limit", 0), totals["max_days"], rem)
                tip = tr("New cards off | New cards left: {count}", count=rem) if days is None else tr("Slowest deck | New cards left: {count}", count=rem)
            else:
                rem, rate = d.get("remaining_new", 0), d.get("new_limit", 0)
                days = None if d.get("is_deleted") else forecast_days(rate, d.get("max_days"), rem)
                tip = tr("New cards off | New cards left: {count}", count=rem) if days is None else tr("{rate} new/day | New cards left: {count}", rate=rate, count=rem)
            c["forecast"] = {"t": "-" if days is None else days_text(days), "s": -1 if days is None else days, "tip": tip}
        if extra_on and not (total and _prepared is not None):  # (View by Deck has no Total row)
            x = _extra_raw(d, total)
            prec = stats_precision()
            na = {"t": "N/A", "s": -1}

            def put(key, fmt):
                if key in on:
                    v = x.get(key)
                    c[key] = na if v is None else {"t": fmt(v), "s": v}

            put("ret_true", lambda v: num("0%" if v == 0 else f"{v:.{prec}f}%"))
            for key in ("rev_young", "rev_mature", "again", "lapses", "best_day", "cards_total", "cards_new",
                        "cards_learning", "cards_young", "cards_mature", "cards_suspended", "cards_buried",
                        "due_today", "backlog"):
                put(key, fmt_num)
            put("reviews_per_day", lambda v: fmt_num(v, prec))
            put("time_per_day", lambda v: format_hours(v, use_decimal=use_decimal, hrs_text=hrs_unit, min_text=min_unit))
            put("reviews_per_active_day", lambda v: fmt_num(v, prec))
            put("time_per_active_day", lambda v: format_hours(v, use_decimal=use_decimal, hrs_text=hrs_unit, min_text=min_unit))
            put("days_learned", lambda v: num(f"{v:.0f}%"))
            put("avg_retrievability", lambda v: num(f"{v:.{prec}f}%"))
            put("avg_stability", lambda v: tr("{value} d", value=fmt_num(v, prec)))
        return c

    rows = [{"kind": "total", "name": tr("Total"), "color": _rgba50(deck_colors.get("total")), "cells": cells(None, True)}]
    for d in ordered:
        did = d.get("did")
        is_deleted = d.get("is_deleted", False)
        if is_deleted:
            key = "deleted" if "deleted" in deck_colors else None
        elif did and str(did) in deck_colors:
            key = str(did)
        elif not did and "folder" in deck_colors:
            key = "folder"
        else:
            key = None
        name = d.get("display_name", d["full_name"])
        rows.append({
            "kind": "deck", "full_name": d["full_name"], "parent": d.get("parent"), "name": name, "deleted": bool(is_deleted),
            "prefix": d.get("tree_prefix", ""), "has_children": bool(d.get("has_children")), "did": did,
            "empty": d["reviews"] == 0 and d["time_ms"] == 0, "color": _rgba50(deck_colors.get(key)) if key else None,
            "cells": cells(d),
        })
    cols = [{"key": "deck", "label": tr("Deck")}] + [{"key": k, "label": tr_name(LABELS[k])} for k in shown]
    _out = {
        "tab": tab, "tabs": [{"title": tr_name(x.get("title", "")), "range": x.get("range")} for x in tabs],
        "columns": cols, "rows": rows, "sort": {"col": col, "desc": desc},
        # every column that can be shown, for the header's right-click menu (Add column)
        "column_choices": {"groups": [[g, tr_name(lbl)] for g, lbl in COL_GROUPS],
                           "all": [[k, tr_name(lbl), grp] for k, lbl, grp, _f in COL_ALL],
                           "counts": show["show_counts"], "defaults": list(COL_DEFAULTS)},
        "expanded": default_expanded(conf),
        "total_bottom": bool(conf.get("Table_Total_Bottom", True)),
        "colors": {"good": good, "bad": bad, "hard": hard, "easy": easy},
        # Settings > General > Table: one row height for every table, and the zebra rows
        "row_height": int(conf.get(Config.GLOBAL_ROW_HEIGHT, t.get("row_height", 30)) or 30),
        "zebra": bool(conf.get(Config.TABLE_ZEBRA, True)),
        "visuals": {
            "buttons": visual_buttons,
            "all": bool(conf.get(Config.RETENTION_VISUAL_ALL, False)),
            "young": bool(conf.get(Config.RETENTION_VISUAL_YOUNG, False)),
            "mature": bool(conf.get(Config.RETENTION_VISUAL_MATURE, False)),
        },
    }
    _t2 = _time.perf_counter()
    _xs = f" new columns={1000 * x_time[0]:.0f}ms" if (need_hist or need_state) else ""
    if _prepared is None:
        _lw(f"table tab={tab} data={1000 * (_t1 - _t0):.0f}ms ({'memo' if _hit else 'computed'}) build={1000 * (_t2 - _t1):.0f}ms{_xs}")
    elif _xs:
        _lw(f"table by deck:{_xs}")
    return _out


def default_expanded(conf):
    """The folders open in the table: the saved ones, or before the user ever toggled one, the parents of every deck
    with reviews (DeepDiveDialog.__init__: an empty saved list means "all closed" only once a folder was toggled)."""
    from ..const.config import Config

    saved = list(conf.get(Config.DETAILS_EXPANDED_DECKS, []) or [])
    if saved or conf.get(Config.DETAILS_EXPANDED_DECKS_SET, False):
        return saved
    try:
        from aqt import mw

        from ..details.logic.data import fetch_dids_with_data

        names = {d.id: d.name for d in mw.col.decks.all_names_and_ids()}
        out = set()
        for did in fetch_dids_with_data():
            if did and did in names:
                parts = names[did].split("::")
                for i in range(1, len(parts)):
                    out.add("::".join(parts[:i]))
        return sorted(out)
    except Exception:
        return saved


def deck_tabs(expanded_names=None, current=None):
    """The tabs of the by-deck view: Collection, Deleted Cards, then the decks (children when their parent is expanded)."""
    from aqt import mw

    from ..const.config import Config
    from ..i18n import deck_title, tr

    conf = _cfg().config
    excluded = conf.get(Config.EXCLUDED_DECKS, []) or []
    # the folders open in the page's table (sent with the request), else the saved ones
    expanded = set(expanded_names if expanded_names is not None else default_expanded(conf))
    # the deck shown: its parents count as open (loader.load_deck_view opens them to select it)
    try:
        if current not in (None, "collection", "__deleted_cards__"):
            cname = mw.col.decks.name(int(current)) or ""
            cp = cname.split("::")
            expanded |= {"::".join(cp[:j]) for j in range(1, len(cp))}
    except Exception:
        pass
    tabs = [{"title": tr("Collection"), "did": "collection"}]
    if conf.get(Config.INCLUDE_DELETED_CARDS, True) and "deleted" not in excluded:
        tabs.append({"title": tr("Deleted Cards"), "did": "__deleted_cards__"})
    decks = sorted(((d.name, d.id) for d in mw.col.decks.all_names_and_ids() if d.id not in excluded), key=lambda x: x[0].lower())
    from .deck_picker import DEFAULT_DECK, hidden_default

    if hidden_default([n for n, _ in decks]):  # Anki's empty Default deck, as in Anki's deck list
        decks = [x for x in decks if x[1] != DEFAULT_DECK]
    names = [n for n, _ in decks]
    # a folder's tab says it has decks under it and whether they are shown (the page folds / unfolds it there)
    cur_name = ""
    try:
        if current not in (None, "collection", "__deleted_cards__"):
            cur_name = mw.col.decks.name(int(current)) or ""
    except Exception:
        pass
    for name, did in decks:
        parts = name.split("::")
        if any("::".join(parts[:j]) not in expanded for j in range(1, len(parts))):
            continue
        kids = any(n.startswith(name + "::") for n in names)
        tabs.append({"title": deck_title(parts[-1]), "did": did, "name": name, "kids": kids, "open": kids and name in expanded,
                     "keep": bool(cur_name) and cur_name.startswith(name + "::")})
    return tabs


def _deck_stats(deck):
    """One deck's rows of every period (View by Deck), kept (_memo) until a new review; (stats, hit)."""
    from ..const.config import Config
    from ..details.logic.data import fetch_deck_stats
    from ..details.logic.tabs import get_active_tabs_config
    from ..config import addon_config as _addon_config

    cfg = _addon_config()
    conf = cfg.config
    tabs_cfg = get_active_tabs_config(cfg)
    is_col = deck == "collection"
    did = None if (is_col or deck == "__deleted_cards__") else int(deck)
    tabs_sig = repr([(t.get("range"), t.get("days"), t.get("custom_type"), t.get("start_date"), t.get("end_date"), t.get("title")) for t in tabs_cfg])
    return _memo(("deck", str(deck), repr(conf.get(Config.EXCLUDED_DECKS, [])), repr(conf.get(Config.SHOW_TRENDS, False)),
                  repr(conf.get(Config.WEEK_START, 0)), bool(conf.get(Config.SPARKLINE_PRECISION, False)), tabs_sig),
                 lambda: fetch_deck_stats(
                     did, tabs_cfg, excluded_dids=conf.get(Config.EXCLUDED_DECKS, []),
                     show_trends=bool(conf.get(Config.SHOW_TRENDS, False)), week_start=conf.get(Config.WEEK_START, 0),
                     spark_precision=conf.get(Config.SPARKLINE_PRECISION, False), is_collection=is_col),
                 ttl=_KEEP_S)


# the moment of the last deck / period change of the Deep Dive window (window._set_scope): the warm-up below waits
# while the user is moving, its reads would slow the charts' own down
LAST_SCOPE = [0.0]
_WARM = {"busy": False, "want": None}


def warm_deck_stats(order):
    """View by Deck: every deck tab's rows read in the background, one deck per task (never sleeping
    or looping across all decks inside mw.taskman's serial worker thread, which would block user clicks)."""
    import threading
    import time

    from aqt import mw
    from aqt.qt import QTimer

    if threading.current_thread() is not threading.main_thread():
        # the table is read in the background: Anki starts background work from the UI thread only (it asserted)
        mw.taskman.run_on_main(lambda: warm_deck_stats(order))
        return
    _WARM["want"] = ["__time_tab0__"] + [str(d) for d in order]
    if _WARM["busy"]:
        return
    _WARM["busy"] = True
    _WARM["done"] = 0

    def _step():
        if not _WARM["want"]:
            _WARM["busy"] = False
            n = _WARM.get("done", 0)
            if n:
                from .trace import trace

                trace(f"table deck warm-up: {n} decks read ahead")
            return
        # Wait on the UI timer (not inside the serial worker thread!) while the user is actively navigating.
        wait_left = 1.2 - (time.monotonic() - LAST_SCOPE[0])
        if wait_left > 0:
            QTimer.singleShot(max(100, int(wait_left * 1000) + 50), _step)
            return
        d = _WARM["want"].pop(0)

        def run_one():
            try:
                if d == "__time_tab0__":
                    table(0, None)
                    return 0
                _v, hit = _deck_stats(d)
                return 0 if hit else 1
            except Exception:
                from ..details.logic.logger import log_swallowed

                log_swallowed()
                return 0

        def on_one(fut):
            try:
                _WARM["done"] = _WARM.get("done", 0) + (fut.result() or 0)
            except Exception:
                pass
            # Yield back to the event loop so any user click's table/stats/data task runs first.
            QTimer.singleShot(25, _step)

        mw.taskman.run_in_background(run_one, on_done=on_one)

    QTimer.singleShot(200, _step)


def _deck_table(deck, sort, expanded=None):
    """Rows = the time spans, for one deck (the normal window's 'View by Deck')."""
    from collections import defaultdict


    from ..const import Period
    from ..details.logic.tabs import get_active_tabs_config
    from ..config import addon_config as _addon_config
    from ..i18n import tr, tr_name

    cfg = _addon_config()
    tabs_cfg = get_active_tabs_config(cfg)
    is_col, is_del = deck == "collection", deck == "__deleted_cards__"
    did = None if (is_col or is_del) else int(deck)
    import time as _time

    from .trace import trace as _lw

    _t0 = _time.perf_counter()
    stats, _hit = _deck_stats(deck)
    _lw(f"table deck={deck} data={1000 * (_time.perf_counter() - _t0):.0f}ms ({'memo' if _hit else 'computed'})")
    tree = {}
    for e in stats:
        r, pr = list(e["res"]), list(e.get("prev_res") or [0] * 13)
        r += [0] * (13 - len(r)); pr += [0] * (13 - len(pr))
        g = lambda a, i: (a[i] or 0) if not isinstance(a[i], str) else 0
        title = tr_name(e.get("title", ""))
        tree[title] = {
            "full_name": title, "display_name": title, "did": None, "parent": None, "has_children": False, "is_deleted": is_del,
            "time_ms": g(r, 1), "reviews": g(r, 2), "passed": g(r, 3), "pass_young": g(r, 4), "rev_young": g(r, 5),
            "pass_mat": g(r, 6), "rev_mat": g(r, 7), "again": g(r, 8), "hard": g(r, 9), "good": g(r, 10), "easy": g(r, 11),
            "active_days": e.get("active_days", g(r, 12)),
            "prev_time_ms": g(pr, 1), "prev_reviews": g(pr, 2), "prev_passed": g(pr, 3), "prev_pass_young": g(pr, 4),
            "prev_rev_young": g(pr, 5), "prev_pass_mat": g(pr, 6), "prev_rev_mat": g(pr, 7),
            "streak_current": e.get("streak_current"), "streak_longest": e.get("streak_longest"),
            "remaining_new": e.get("remaining_new", 0), "new_limit": e.get("limit", 0), "max_days": e.get("max_days"),
            "range": e.get("range_type"),
            # the new columns read the history cache: this deck over this row's span
            "_ctx_did": -1 if is_del else did,
            "_span": next((x for x in tabs_cfg if tr_name(x.get("title", "")) == title), {"range": e.get("range_type")}),
        }
    out = table(0, {"col": "none", "desc": False}, _prepared={"results": [], "totals": defaultdict(int), "tree_data": tree})
    ranges = {k: v.get("range") for k, v in tree.items()}
    out["rows"] = [dict(r, kind="span", empty=False, color=None, full_name=r["full_name"], prefix="", has_children=False,
                        total=(ranges.get(r["full_name"]) == Period.TOTAL), range=ranges.get(r["full_name"]))
                   for r in out["rows"] if r.get("kind") == "deck"]
    out["columns"][0]["label"] = tr("Period")
    out["deck_tabs"] = deck_tabs(expanded, deck)
    try:
        warm_deck_stats([deck] + [t["did"] for t in out["deck_tabs"] if str(t["did"]) != str(deck)])
    except Exception:
        from ..details.logic.logger import log_swallowed

        log_swallowed()
    out["tab"] = next((i for i, t in enumerate(out["deck_tabs"]) if str(t["did"]) == str(deck)), 0)
    out["tabs"] = [{k: t[k] for k in ("title", "did", "name", "kids", "open", "keep") if k in t} for t in out["deck_tabs"]]
    out["mode"] = "deck"
    out["sort"] = {"col": "none", "desc": False}
    return out


def _rgba50(color):
    """A deck color as the translucent row background the table uses (alpha 50 of 255)."""
    if not color:
        return None
    c = str(color).strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) == 6:
        try:
            return "rgba(%d,%d,%d,%.3f)" % (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 50 / 255)
        except ValueError:
            return None
    return None


def _add_extras():
    from .extras_providers import EXTRA_PROVIDERS

    PROVIDERS.update(EXTRA_PROVIDERS)


_add_extras()


def review_events(deck, t0, t1):
    """One entry per review in [t0, t1) ms: (time, answer ms, button, kind, card id), the review types hidden on
    Activity left out; None when there are too many."""
    from ..details.logic.data.transforms.activity_series import normalize_hidden_types
    from ..details.logic.history_provider import HistoryProvider
    from ..details.logic.history_provider.ops.review_events import fetch_review_events

    events = fetch_review_events(HistoryProvider, _cfg(), None if deck == -1 else deck, deck == -1, int(t0), int(t1))
    if events is None:
        return {"events": None}
    hidden = normalize_hidden_types(_setting("activity", "hidden_review_types", None))
    if hidden:
        kinds = ("learn", "young", "mature", "relearn", "cram")
        events = [e for e in events if kinds[e[3]] not in hidden]
    return {"events": [list(e) for e in events]}
