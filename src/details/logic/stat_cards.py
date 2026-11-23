# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ...const import Config
from ...utils import format_hours
from .formatting import fmt_num, fmt_percent_or_na, stats_precision
from ...i18n import N_, num, tr, tr_name

DEFAULT_STATS_PRECISION = 2


STAT_CARD_INFO_MAP = {
    Config.DEEP_DIVE_SHOW_TIME: (N_("Total Time"), "#8ab4f8"),
    Config.DEEP_DIVE_SHOW_REVIEWS: (N_("Reviews"), "#FF9800"),
    Config.DEEP_DIVE_SHOW_AVG_TIME: (N_("Time/Card"), "#06b6d4"),
    Config.DEEP_DIVE_SHOW_RET_ALL: (N_("Retention"), "#22c55e"),
    Config.DEEP_DIVE_SHOW_RET_YOUNG: (N_("Young"), "#00BCD4"),
    Config.DEEP_DIVE_SHOW_RET_MAT: (N_("Mature"), "#4caf50"),
    Config.DASH_SHOW_TIME: (N_("Total Time"), "#8ab4f8"),
    Config.DASH_SHOW_REVIEWS: (N_("Reviews"), "#FF9800"),
    Config.DASH_SHOW_AVG_TIME: (N_("Time/Card"), "#06b6d4"),
    Config.DASH_SHOW_RET_ALL: (N_("Retention"), "#22c55e"),
    Config.DASH_SHOW_RET_YOUNG: (N_("Young"), "#00BCD4"),
    Config.DASH_SHOW_RET_MAT: (N_("Mature"), "#4caf50"),
    Config.DASH_SHOW_STREAK: (N_("Streak"), "#F44336"),
    Config.DASH_SHOW_ACTIVE_DAYS: (N_("Active Days"), "#e91e63"),
    Config.DASH_SHOW_DAYS_LEARNED: (N_("Days Learned"), "#e91e63"),
    Config.DASH_SHOW_LONGEST_STREAK: (N_("Longest Streak"), "#F44336"),
    Config.DASH_SHOW_REVIEWS_PER_DAY: (N_("Reviews/Day"), "#FF9800"),
    Config.DASH_SHOW_TIME_PER_DAY: (N_("Time/Day"), "#8ab4f8"),
    Config.DASH_SHOW_REVIEWS_PER_ACTIVE_DAY: (N_("Reviews/Active Day"), "#FF9800"),
    Config.DASH_SHOW_TIME_PER_ACTIVE_DAY: (N_("Time/Active Day"), "#8ab4f8"),
    Config.DASH_SHOW_RET_TRUE: (N_("True Retention"), "#9fa8da"),
    Config.DASH_SHOW_REV_YOUNG: (N_("Young Reviews"), "#00BCD4"),
    Config.DASH_SHOW_REV_MATURE: (N_("Mature Reviews"), "#4caf50"),
    Config.DASH_SHOW_AGAIN: (N_("Again"), "#f44336"),
    Config.DASH_SHOW_BEST_DAY: (N_("Best Day"), "#FF9800"),
    Config.DASH_SHOW_CARDS_TOTAL: (N_("Total Cards"), "#669ff7"),
    Config.DASH_SHOW_CARDS_NEW: (N_("New Cards"), "#1976d2"),
    Config.DASH_SHOW_CARDS_LEARNING: (N_("Learning Cards"), "#ff9800"),
    Config.DASH_SHOW_CARDS_YOUNG: (N_("Young Cards"), "#8bc34a"),
    Config.DASH_SHOW_CARDS_MATURE: (N_("Mature Cards"), "#4caf50"),
    Config.DASH_SHOW_CARDS_SUSPENDED: (N_("Suspended Cards"), "#fdd835"),
    Config.DASH_SHOW_CARDS_BURIED: (N_("Buried Cards"), "#9e9e9e"),
    Config.DASH_SHOW_CARDS_DELETED: (N_("Deleted Cards"), "#8d95a5"),
    Config.DASH_SHOW_DUE_TODAY: (N_("Due Today"), "#4ade80"),
    Config.DASH_SHOW_BACKLOG: (N_("Backlog"), "#f59e0b"),
    Config.DASH_SHOW_AVG_RETRIEVABILITY: (N_("Avg Retrievability"), "#4cd964"),
    Config.DASH_SHOW_AVG_STABILITY: (N_("Avg Stability"), "#5ac8fa"),
    Config.DASH_SHOW_LAPSES: (N_("Lapses"), "#f44336"),
    Config.DEEP_DIVE_SHOW_STREAK: (N_("Streak"), "#F44336"),
    Config.DEEP_DIVE_SHOW_ACTIVE_DAYS: (N_("Active Days"), "#e91e63"),
}


# The per-day cards and their "days studied only" twin: right-click "Active days only" turns a card into the other.
ACTIVE_DAY_TWINS = {
    Config.DASH_SHOW_REVIEWS_PER_DAY: Config.DASH_SHOW_REVIEWS_PER_ACTIVE_DAY,
    Config.DASH_SHOW_TIME_PER_DAY: Config.DASH_SHOW_TIME_PER_ACTIVE_DAY,
}


def active_day_twin(stat_key):
    """(the other card's key, True when stat_key is the active-days one), or None for the other cards."""
    for every_day, active in ACTIVE_DAY_TWINS.items():
        if stat_key == every_day:
            return active, False
        if stat_key == active:
            return every_day, True
    return None


def get_stat_card_name(stat_key):
    """English default name of a stat card: the form saved in the settings."""
    return STAT_CARD_INFO_MAP.get(stat_key, (N_("Stat"), "#808080"))[0]


def get_stat_card_info(stat_key):
    """(shown default name, default color) of a stat card."""
    name, color = STAT_CARD_INFO_MAP.get(stat_key, (N_("Stat"), "#808080"))
    return tr_name(name), color


def get_stat_card_default_title(stat_key):
    """Shown default name of a stat card."""
    return get_stat_card_info(stat_key)[0]


def stat_card_label_to_save(stat_key, shown_label):
    """The label to save for a stat card: its English name when the shown label is the
    default one (so it follows the language), the user's text otherwise."""
    if shown_label == get_stat_card_default_title(stat_key):
        return get_stat_card_name(stat_key)
    return shown_label


DASHBOARD_CARD_SPECS = (
    {"attr": "card_time", "field": "total_time", "config_key": Config.DASH_SHOW_TIME, "stat_type": Config.COLOR_TIME},
    {"attr": "card_reviews", "field": "reviews", "config_key": Config.DASH_SHOW_REVIEWS, "stat_type": Config.COLOR_REVIEWS},
    {"attr": "card_ret_all", "field": "ret_all", "config_key": Config.DASH_SHOW_RET_ALL, "stat_type": Config.COLOR_RETENTION},
    {"attr": "card_ret_young", "field": "ret_young", "config_key": Config.DASH_SHOW_RET_YOUNG, "stat_type": Config.COLOR_YOUNG},
    {"attr": "card_ret_mat", "field": "ret_mat", "config_key": Config.DASH_SHOW_RET_MAT, "stat_type": Config.COLOR_MATURE},
    {"attr": "card_avg_time", "field": "avg_time", "config_key": Config.DASH_SHOW_AVG_TIME, "stat_type": Config.COLOR_AVG_TIME},
    {"attr": "card_streak", "field": "streak", "config_key": Config.DASH_SHOW_STREAK, "stat_type": Config.COLOR_STREAK},
    {"attr": "card_active_days", "field": "active_days", "config_key": Config.DASH_SHOW_ACTIVE_DAYS, "stat_type": Config.COLOR_ACTIVE_DAYS},
    {"attr": "card_days_learned", "field": "days_learned", "config_key": Config.DASH_SHOW_DAYS_LEARNED, "stat_type": Config.COLOR_ACTIVE_DAYS},
    {"attr": "card_longest_streak", "field": "longest_streak", "config_key": Config.DASH_SHOW_LONGEST_STREAK, "stat_type": Config.COLOR_STREAK},
    {"attr": "card_reviews_per_day", "field": "reviews_per_day", "config_key": Config.DASH_SHOW_REVIEWS_PER_DAY, "stat_type": Config.COLOR_REVIEWS},
    {"attr": "card_time_per_day", "field": "time_per_day", "config_key": Config.DASH_SHOW_TIME_PER_DAY, "stat_type": Config.COLOR_TIME},
    {"attr": "card_reviews_per_active_day", "field": "reviews_per_active_day", "config_key": Config.DASH_SHOW_REVIEWS_PER_ACTIVE_DAY, "stat_type": Config.COLOR_REVIEWS},
    {"attr": "card_time_per_active_day", "field": "time_per_active_day", "config_key": Config.DASH_SHOW_TIME_PER_ACTIVE_DAY, "stat_type": Config.COLOR_TIME},
    {"attr": "card_ret_true", "field": "ret_true", "config_key": Config.DASH_SHOW_RET_TRUE, "stat_type": Config.COLOR_CRAM},
    {"attr": "card_rev_young", "field": "rev_young", "config_key": Config.DASH_SHOW_REV_YOUNG, "stat_type": Config.COLOR_YOUNG},
    {"attr": "card_rev_mature", "field": "rev_mature", "config_key": Config.DASH_SHOW_REV_MATURE, "stat_type": Config.COLOR_MATURE},
    {"attr": "card_again", "field": "again", "config_key": Config.DASH_SHOW_AGAIN, "stat_type": Config.COLOR_RELEARN},
    {"attr": "card_best_day", "field": "best_day", "config_key": Config.DASH_SHOW_BEST_DAY, "stat_type": Config.COLOR_REVIEWS},
    {"attr": "card_cards_total", "field": "cards_total", "config_key": Config.DASH_SHOW_CARDS_TOTAL, "stat_type": Config.COLOR_BAR},
    {"attr": "card_cards_new", "field": "cards_new", "config_key": Config.DASH_SHOW_CARDS_NEW, "stat_type": Config.COLOR_NEW},
    {"attr": "card_cards_learning", "field": "cards_learning", "config_key": Config.DASH_SHOW_CARDS_LEARNING, "stat_type": Config.COLOR_LEARN},
    {"attr": "card_cards_young", "field": "cards_young", "config_key": Config.DASH_SHOW_CARDS_YOUNG, "stat_type": Config.COLOR_YOUNG},
    {"attr": "card_cards_mature", "field": "cards_mature", "config_key": Config.DASH_SHOW_CARDS_MATURE, "stat_type": Config.COLOR_MATURE},
    {"attr": "card_cards_suspended", "field": "cards_suspended", "config_key": Config.DASH_SHOW_CARDS_SUSPENDED, "stat_type": Config.COLOR_SUSPENDED},
    {"attr": "card_cards_buried", "field": "cards_buried", "config_key": Config.DASH_SHOW_CARDS_BURIED, "stat_type": Config.COLOR_BURIED},
    {"attr": "card_cards_deleted", "field": "cards_deleted", "config_key": Config.DASH_SHOW_CARDS_DELETED, "stat_type": Config.COLOR_DELETED},
    {"attr": "card_due_today", "field": "due_today", "config_key": Config.DASH_SHOW_DUE_TODAY, "stat_type": Config.COLOR_FUTURE_DUE},
    {"attr": "card_backlog", "field": "backlog", "config_key": Config.DASH_SHOW_BACKLOG, "stat_type": Config.COLOR_BACKLOG},
    {"attr": "card_avg_retrievability", "field": "avg_retrievability", "config_key": Config.DASH_SHOW_AVG_RETRIEVABILITY, "stat_type": Config.COLOR_GOOD},
    {"attr": "card_avg_stability", "field": "avg_stability", "config_key": Config.DASH_SHOW_AVG_STABILITY, "stat_type": Config.COLOR_EASY},
    {"attr": "card_lapses", "field": "lapses", "config_key": Config.DASH_SHOW_LAPSES, "stat_type": Config.COLOR_RELEARN},
)


STAT_VALUE_FIELD_BINDINGS = (
    ("total_time", Config.DEEP_DIVE_SHOW_TIME, Config.DASH_SHOW_TIME),
    ("reviews", Config.DEEP_DIVE_SHOW_REVIEWS, Config.DASH_SHOW_REVIEWS),
    ("avg_time", Config.DEEP_DIVE_SHOW_AVG_TIME, Config.DASH_SHOW_AVG_TIME),
    ("ret_all", Config.DEEP_DIVE_SHOW_RET_ALL, Config.DASH_SHOW_RET_ALL),
    ("ret_young", Config.DEEP_DIVE_SHOW_RET_YOUNG, Config.DASH_SHOW_RET_YOUNG),
    ("ret_mat", Config.DEEP_DIVE_SHOW_RET_MAT, Config.DASH_SHOW_RET_MAT),
    ("streak", Config.DEEP_DIVE_SHOW_STREAK, Config.DASH_SHOW_STREAK),
    ("active_days", Config.DEEP_DIVE_SHOW_ACTIVE_DAYS, Config.DASH_SHOW_ACTIVE_DAYS),
    # Cards added later have no Deep Dive switch of their own (dd_key None).
    ("days_learned", None, Config.DASH_SHOW_DAYS_LEARNED),
    ("longest_streak", None, Config.DASH_SHOW_LONGEST_STREAK),
    ("reviews_per_day", None, Config.DASH_SHOW_REVIEWS_PER_DAY),
    ("time_per_day", None, Config.DASH_SHOW_TIME_PER_DAY),
    ("reviews_per_active_day", None, Config.DASH_SHOW_REVIEWS_PER_ACTIVE_DAY),
    ("time_per_active_day", None, Config.DASH_SHOW_TIME_PER_ACTIVE_DAY),
    ("ret_true", None, Config.DASH_SHOW_RET_TRUE),
    ("rev_young", None, Config.DASH_SHOW_REV_YOUNG),
    ("rev_mature", None, Config.DASH_SHOW_REV_MATURE),
    ("again", None, Config.DASH_SHOW_AGAIN),
    ("best_day", None, Config.DASH_SHOW_BEST_DAY),
    ("cards_total", None, Config.DASH_SHOW_CARDS_TOTAL),
    ("cards_new", None, Config.DASH_SHOW_CARDS_NEW),
    ("cards_learning", None, Config.DASH_SHOW_CARDS_LEARNING),
    ("cards_young", None, Config.DASH_SHOW_CARDS_YOUNG),
    ("cards_mature", None, Config.DASH_SHOW_CARDS_MATURE),
    ("cards_suspended", None, Config.DASH_SHOW_CARDS_SUSPENDED),
    ("cards_buried", None, Config.DASH_SHOW_CARDS_BURIED),
    ("cards_deleted", None, Config.DASH_SHOW_CARDS_DELETED),
    ("due_today", None, Config.DASH_SHOW_DUE_TODAY),
    ("backlog", None, Config.DASH_SHOW_BACKLOG),
    ("avg_retrievability", None, Config.DASH_SHOW_AVG_RETRIEVABILITY),
    ("avg_stability", None, Config.DASH_SHOW_AVG_STABILITY),
    ("lapses", None, Config.DASH_SHOW_LAPSES),
)


# Card-state fields: sums of the per-deck card counts (they do not depend on the time span).
CARD_STATE_FIELDS = {
    "cards_total": ("total",),
    "cards_new": ("new",),
    "cards_learning": ("learn", "relearn"),
    "cards_young": ("young",),
    "cards_mature": ("mature",),
    "cards_suspended": ("suspended",),
    "cards_buried": ("buried",),
    "cards_deleted": ("deleted",),
}
# Fields read from the deck's current state (card counts, due cards, FSRS), whatever the time span.
SCHEDULE_FIELDS = frozenset({"due_today", "backlog", "avg_retrievability", "avg_stability"})
DECK_STATE_FIELDS = frozenset(CARD_STATE_FIELDS) | SCHEDULE_FIELDS
DECK_STATE_STAT_KEYS = frozenset(
    dash_key for field, _dd, dash_key in STAT_VALUE_FIELD_BINDINGS if field in DECK_STATE_FIELDS
)


def deck_state_from_context(ctx):
    """The parts of a history context that the deck-state cards read."""
    ctx = ctx or {}
    return {"counts": ctx.get("counts"), "future_due": ctx.get("future_due"), "fsrs": ctx.get("fsrs")}


def _weighted_mean(hist):
    total = sum(hist.values())
    return sum(k * v for k, v in hist.items()) / total if total > 0 else None


def _today():
    try:
        from aqt import mw

        return int(mw.col.sched.today)
    except Exception:
        return None


def schedule_values(future_due, fsrs, prec, today=None):
    """Due today, backlog and FSRS averages; N/A for what is not in the data.

    The cache keeps the due cards by Anki due day (days since the collection was created,
    the cards of Anki's Future Due graph, learning cards included), not by days from today:
    today's are those due on today's day number, the backlog those due before it."""
    out = dict.fromkeys(SCHEDULE_FIELDS, "N/A")
    dist = (future_due or {}).get("distribution") if isinstance(future_due, dict) else None
    today = _today() if today is None else today
    if isinstance(dist, dict) and today is not None:
        due_today = backlog = 0
        for day, count in dist.items():
            try:
                day = int(day)
            except (TypeError, ValueError):
                continue
            if day < 0 or day >= 1000000000:
                continue  # invalid (an older cache could still hold a learning card's timestamp)
            if day == today:
                due_today += count or 0
            elif day < today:
                backlog += count or 0
        out["due_today"] = fmt_num(due_today)
        out["backlog"] = fmt_num(backlog)
    fsrs = fsrs if isinstance(fsrs, dict) else {}
    ret_hist = fsrs.get("retrievability") or {}
    ret_total = sum(ret_hist.values())
    # 1% bins 0..99 represent [k, k+1): use bin midpoint k+0.5 (100 stays 100), matching Deck Table & chart.
    retrievability = (sum((min(100.0, k + 0.5) if k < 100 else 100.0) * v for k, v in ret_hist.items()) / ret_total) if ret_total > 0 else None
    if retrievability is not None:
        out["avg_retrievability"] = num(f"{retrievability:.{int(prec)}f}%")
    stability = _weighted_mean(fsrs.get("stability") or {})
    if stability is not None:
        out["avg_stability"] = tr("{value} d", value=fmt_num(stability, prec))
    return out


def card_state_values(counts):
    """Card-state card strings from a card-counts dict; N/A when the counts are not available."""
    if not isinstance(counts, dict):
        return {field: "N/A" for field in CARD_STATE_FIELDS}
    return {
        field: fmt_num(sum(counts.get(key, 0) or 0 for key in keys))
        for field, keys in CARD_STATE_FIELDS.items()
    }


# Fields that need the day-by-day history, not just the period totals.
HISTORY_DERIVED_FIELDS = frozenset({"days_learned", "longest_streak", "reviews_per_day", "time_per_day", "best_day",
                                    "reviews_per_active_day", "time_per_active_day"})
HISTORY_DERIVED_STAT_KEYS = frozenset(
    dash_key for field, _dd, dash_key in STAT_VALUE_FIELD_BINDINGS if field in HISTORY_DERIVED_FIELDS
)


def history_day_stats(history):
    """Day-level figures from dense history rows: period length, studied days, longest run, best day."""
    from datetime import date

    days = {}
    for h in history:
        try:
            days[date.fromisoformat(str(h.get("logical_date")))] = h.get("reviews", 0) or 0
        except Exception:
            continue
    if not days:
        return {"days_in_period": 0, "active_days": 0, "longest_streak": 0, "best_day": 0}
    first, last = min(days), max(days)
    longest = run = 0
    prev = None
    for d in sorted(d for d, n in days.items() if n > 0):
        run = run + 1 if prev is not None and (d - prev).days == 1 else 1
        longest = max(longest, run)
        prev = d
    return {
        "days_in_period": (last - first).days + 1,
        "active_days": sum(1 for n in days.values() if n > 0),
        "longest_streak": longest,
        "best_day": max(days.values()),
    }


def build_dashboard_history_totals(history_slice, *, streak_current=0):
    """Build canonical dashboard totals payload directly from review-history rows."""
    history = history_slice or []
    total_time_ms = sum(h.get("time_ms", 0) for h in history)
    day_stats = history_day_stats(history)
    return {
        "again": sum(h.get("again", 0) for h in history),
        "days_in_period": day_stats["days_in_period"],
        "period_active_days": day_stats["active_days"],
        "longest_streak": day_stats["longest_streak"],
        "best_day": day_stats["best_day"],
        "time": total_time_ms / (1000 * 3600),
        "rev": sum(h.get("reviews", 0) for h in history),
        "pass": sum(h.get("passed", 0) for h in history),
        "pass_young": sum(h.get("pass_young", 0) for h in history),
        "rev_young": sum(h.get("rev_young", 0) for h in history),
        "pass_mat": sum(h.get("pass_mat", 0) for h in history),
        "rev_mat": sum(h.get("rev_mat", 0) for h in history),
        "streak_current": streak_current,
        "active_days": len(set(h.get("logical_date") for h in history if h.get("reviews", 0) > 0)),
    }


def build_dashboard_stat_values(
    totals,
    *,
    use_decimal=True,
    hrs_unit="hrs",
    min_unit="min",
    prec=2,
    time_precision=None,
):
    """Build canonical dashboard stat strings from totals payload."""
    data = totals or {}
    if prec is None:
        prec = stats_precision(DEFAULT_STATS_PRECISION)
    if time_precision is None:
        time_precision = prec
    t_rev = data.get("rev", 0)
    t_pass = data.get("pass", 0)
    t_pass_young = data.get("pass_young", 0)
    t_rev_young = data.get("rev_young", 0)
    t_pass_mat = data.get("pass_mat", 0)
    t_rev_mat = data.get("rev_mat", 0)
    return {
        "total_time": format_hours(
            data.get("time", 0),
            precision=time_precision,
            use_decimal=use_decimal,
            hrs_text=hrs_unit,
            min_text=min_unit,
        ),
        "reviews": fmt_num(t_rev),
        "avg_time": (tr("{value}s", value=fmt_num(((float(data.get('time', 0) or 0.0) * 3600.0) / t_rev), prec)) if t_rev > 0 else "N/A"),
        "ret_all": fmt_percent_or_na(t_pass, t_rev, prec),
        "ret_young": fmt_percent_or_na(t_pass_young, t_rev_young, prec),
        "ret_mat": fmt_percent_or_na(t_pass_mat, t_rev_mat, prec),
        "streak": fmt_num(data.get("streak_current", 0)),
        "active_days": fmt_num(data.get("active_days", 0)),
        "days_learned": fmt_percent_or_na(data.get("period_active_days", data.get("active_days", 0)), data.get("days_in_period"), 0),
        "longest_streak": _fmt_or_na(data.get("longest_streak", data.get("streak_longest"))),
        "reviews_per_day": _per_day(data, t_rev, lambda v: fmt_num(v, prec)),
        "time_per_day": _per_day(
            data, float(data.get("time", 0) or 0.0),
            lambda v: format_hours(v, precision=time_precision, use_decimal=use_decimal, hrs_text=hrs_unit, min_text=min_unit),
        ),
        "reviews_per_active_day": _per_active_day(data, t_rev, lambda v: fmt_num(v, prec)),
        "time_per_active_day": _per_active_day(
            data, float(data.get("time", 0) or 0.0),
            lambda v: format_hours(v, precision=time_precision, use_decimal=use_decimal, hrs_text=hrs_unit, min_text=min_unit),
        ),
        "ret_true": fmt_percent_or_na(t_pass_young + t_pass_mat, t_rev_young + t_rev_mat, prec),
        "rev_young": fmt_num(t_rev_young),
        "rev_mature": fmt_num(t_rev_mat),
        "again": _fmt_or_na(data.get("again")),
        "best_day": _fmt_or_na(data.get("best_day")),
        **card_state_values(data.get("counts")),
        **schedule_values(data.get("future_due"), data.get("fsrs"), prec),
        "lapses": fmt_num((t_rev_young + t_rev_mat) - (t_pass_young + t_pass_mat)),
    }


def _fmt_or_na(value):
    return "N/A" if value is None else fmt_num(value)


def _per_day(data, total, fmt):
    days = data.get("days_in_period") or 0
    return fmt(total / days) if days > 0 else "N/A"


def active_days_of(data):
    """The days studied in the period (the day-level count when the history was read, else the totals')."""
    return data.get("period_active_days", data.get("active_days", 0)) or 0


def _per_active_day(data, total, fmt):
    days = active_days_of(data)
    return fmt(total / days) if days > 0 else "N/A"


def map_stat_fields_to_config_keys(values_by_field):
    """Expand canonical stat fields into both DASH_* and DEEP_DIVE_* config-keyed map."""
    src = values_by_field or {}
    out = {}
    for field_name, dd_key, dash_key in STAT_VALUE_FIELD_BINDINGS:
        val = src.get(field_name, "...")
        if dd_key:
            out[dd_key] = val
        out[dash_key] = val
    return out


def merge_stat_card_style_config(base_cfg, local_overrides=None):
    """Return merged stat-card style config (global + Facecards_/Dashboard_ overrides)."""
    merged = dict(base_cfg or {})
    for k, v in dict(local_overrides or {}).items():
        if not isinstance(k, str):
            continue
        if k.startswith("Facecards_") or k.startswith("Dashboard_"):
            merged[k] = v
    return merged


def get_dashboard_local_stat_style(active_conf, config_key):
    """Read per-dashboard stat style entry and normalize required flags."""
    styles_map = (active_conf or {}).get(Config.DASH_STAT_STYLES, {})
    local_style = {}
    if isinstance(styles_map, dict):
        entry = styles_map.get(str(config_key))
        if isinstance(entry, dict):
            local_style = dict(entry)
    local_style.setdefault("use_custom_style", bool(local_style.get("use_custom_style", False)))
    return local_style


