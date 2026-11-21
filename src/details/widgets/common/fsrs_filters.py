# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ....i18n import num, tr, tr_n, N_, tr_name

DEFAULT_FSRS_FILTER_IDX = 2
FSRS_FILTER_MODES = ("1_month", "50_percent", "95_percent", "all")
FSRS_FILTER_LABELS_SHORT = (N_("1m"), "50%", "95%", N_("all"))
FSRS_FILTER_LABELS_LONG = (N_("1 month"), "50%", "95%", N_("all"))


# The four radio buttons can be changed per chart (Stability and Review Intervals).
# Modes: "d<N>" and "1_month" cap the axis at N days, "<N>_percent" / "p<N>" cap it at
# that share of the cards, "all" shows everything. Order here is the display order.
FSRS_FILTER_CHOICES = (
    ("d7", N_("1 week"), N_("1w")),
    ("d14", N_("2 weeks"), N_("2w")),
    ("1_month", N_("1 month"), N_("1m")),
    ("d90", N_("3 months"), N_("3m")),
    ("d365", N_("1 year"), N_("1y")),
    ("50_percent", N_("50%"), N_("50%")),
    ("p80", N_("80%"), N_("80%")),
    ("p90", N_("90%"), N_("90%")),
    ("95_percent", N_("95%"), N_("95%")),
    ("p99", N_("99%"), N_("99%")),
    ("all", N_("all"), N_("all")),
)
_FSRS_CANONICAL = {"d31": "1_month", "p50": "50_percent", "p95": "95_percent"}


def parse_fsrs_mode(mode):
    """Return ("days", n), ("percent", n) or ("all", 0) for a mode string, else None.

    Custom values: "d<N>" (1..9999 days) and "p<N>" (1..99 percent).
    """
    mode = _FSRS_CANONICAL.get(str(mode), str(mode))
    if mode == "all":
        return ("all", 0)
    if mode == "1_month":
        return ("days", 31)
    if mode == "50_percent":
        return ("percent", 50)
    if mode == "95_percent":
        return ("percent", 95)
    if len(mode) > 1 and mode[1:].isdigit():
        n = int(mode[1:])
        if mode[0] == "d" and 1 <= n <= 9999:
            return ("days", n)
        if mode[0] == "p" and 1 <= n <= 99:
            return ("percent", n)
    return None


def canonical_fsrs_mode(mode):
    return _FSRS_CANONICAL.get(str(mode), str(mode))


def _fsrs_mode_sort_key(mode):
    kind, n = parse_fsrs_mode(mode)
    return ({"days": 0, "percent": 1, "all": 2}[kind], n)


def fsrs_mode_labels(mode):
    """(long, short) label of a mode."""
    for m, long_, short in FSRS_FILTER_CHOICES:
        if m == mode:
            return tr_name(long_), tr_name(short)
    kind, n = parse_fsrs_mode(mode)
    return (tr_n("{n} day", "{n} days", n), tr("{n}d", n=n)) if kind == "days" else (num(f"{n}%"), num(f"{n}%"))


def normalize_fsrs_filter_modes(modes):
    """2 to 8 distinct valid modes in display order; anything unusable gives the defaults."""
    try:
        values = [str(m) for m in (modes or [])]
    except Exception:
        return FSRS_FILTER_MODES
    values = [canonical_fsrs_mode(m) for m in values]
    if (not 2 <= len(values) <= 8 or len(set(values)) != len(values)
            or any(parse_fsrs_mode(m) is None for m in values)):
        return FSRS_FILTER_MODES
    return tuple(sorted(values, key=_fsrs_mode_sort_key))


# The charts with these buttons share one list of them, in the Deep Dive and on the main screen (Future Due has
# buttons of its own kind, days ahead): the one chosen stays each chart's own.
SHARED_FILTER_TYPES = ("stability", "review_intervals", "interval_load", "lapse_distribution", "review_distribution",
                       "learning_steps", "time_distribution", "interval_history", "stability_history")


def shared_fsrs_filter_modes(conf=None):
    """The Range Buttons the charts share (Config.SHARED_FILTER_MODES, saved by the widget settings' Save). Before
    any was saved there, the first list a chart was given (its Deep Dive settings, then a pinned chart's), so a list
    made for one chart is the one they all show; None: none was ever given (the defaults)."""
    try:
        if conf is None:
            from .... import config as _c

            conf = _c.read_config_dict()
            # a settings window open: the config it shows (set_live_config_override) may not hold it; the saved one
            if _c._LIVE_CONFIG_OVERRIDE[0] is not None and not conf.get("Shared_Filter_Modes"):
                conf = _c.addon_config().config
        shared = conf.get("Shared_Filter_Modes")
        if shared:
            return shared
        sets = conf.get("Deep_Dive_Widget_Settings") or {}
        for t in SHARED_FILTER_TYPES:
            for key in (t + "_g", t):
                sec = sets.get(key)
                own = sec.get("filter_modes") if isinstance(sec, dict) else None
                if own:
                    return own
        for d in conf.get("Pinned_Widgets") or ():
            if isinstance(d, dict) and d.get("type") in SHARED_FILTER_TYPES and d.get("filter_modes"):
                return d["filter_modes"]
    except Exception:
        from ...logic.logger import log_swallowed

        log_swallowed()
    return None


def resolve_fsrs_filters(modes=None):
    """Return (modes, short_labels, long_labels) for the radio buttons: the list the charts share
    (shared_fsrs_filter_modes), else the one given."""
    shared = shared_fsrs_filter_modes()
    if shared:
        modes = shared
    resolved = normalize_fsrs_filter_modes(modes)
    return resolved, tuple(fsrs_mode_labels(m)[1] for m in resolved), tuple(fsrs_mode_labels(m)[0] for m in resolved)


def default_fsrs_filter_idx(modes=FSRS_FILTER_MODES):
    return modes.index("95_percent") if "95_percent" in modes else min(DEFAULT_FSRS_FILTER_IDX, len(modes) - 1)


def clamp_fsrs_filter_idx(idx, default_idx=DEFAULT_FSRS_FILTER_IDX, count=len(FSRS_FILTER_MODES)):
    try:
        resolved = int(idx)
    except Exception:
        resolved = int(default_idx)

    if resolved < 0 or resolved >= count:
        return int(default_idx)
    return resolved


def get_fsrs_filter_mode(idx, default_idx=DEFAULT_FSRS_FILTER_IDX, modes=FSRS_FILTER_MODES):
    return modes[clamp_fsrs_filter_idx(idx, default_idx=default_idx, count=len(modes))]


def resolve_fsrs_filter_choice(idx, default_idx=None, modes=FSRS_FILTER_MODES):
    if default_idx is None:
        default_idx = default_fsrs_filter_idx(modes)
    resolved_idx = clamp_fsrs_filter_idx(idx, default_idx=default_idx, count=len(modes))
    return resolved_idx, get_fsrs_filter_mode(resolved_idx, default_idx=default_idx, modes=modes)


def compute_fsrs_distribution_percentiles(
    dist,
    *,
    percentiles=(0.50, 0.95),
    positive_only=True,
    default_value=30,
):
    values = {}
    valid_items = []
    for key, raw_count in (dist or {}).items():
        try:
            day = int(key)
            count = float(raw_count or 0.0)
        except Exception:
            continue
        if positive_only and day <= 0:
            continue
        if count <= 0:
            continue
        valid_items.append((day, count))

    valid_items.sort(key=lambda item: item[0])
    total = float(sum(count for _, count in valid_items))
    for pct in percentiles or ():
        values[float(pct)] = int(default_value)

    if total <= 0 or not valid_items:
        return {"total": 0.0, "values": values, "items": valid_items}

    ordered_pcts = sorted(float(p) for p in (percentiles or ()))
    run_sum = 0.0
    remaining = list(ordered_pcts)
    for day, count in valid_items:
        run_sum += count
        while remaining and run_sum >= total * remaining[0]:
            values[remaining.pop(0)] = int(day)
        if not remaining:
            break

    if remaining:
        last_day = int(valid_items[-1][0])
        for pct in remaining:
            values[pct] = last_day

    return {"total": total, "values": values, "items": valid_items}


def resolve_fsrs_filter_max_days(
    filter_mode,
    *,
    dist,
    p50=None,
    p95=None,
    one_month_days=31,
    all_fallback_days=30,
    invalid_fallback_days=31,
    minimum_days=1,
    positive_only=True,
):
    mode = str(filter_mode or "95_percent")
    if len(mode) > 1 and mode[0] == "d" and mode[1:].isdigit():
        max_days = int(mode[1:])
    elif len(mode) > 1 and mode[0] == "p" and mode[1:].isdigit():
        pct = int(mode[1:]) / 100.0
        found = compute_fsrs_distribution_percentiles(
            dist, percentiles=(pct,), positive_only=positive_only, default_value=all_fallback_days
        )
        max_days = int(found["values"].get(pct, all_fallback_days))
    elif mode == "1_month":
        max_days = int(one_month_days)
    elif mode == "50_percent":
        max_days = int(p50 if p50 is not None else all_fallback_days)
    elif mode == "95_percent":
        max_days = int(p95 if p95 is not None else all_fallback_days)
    elif mode == "all":
        max_days = max(dist.keys()) if dist else int(all_fallback_days)
    else:
        max_days = int(invalid_fallback_days)

    if int(max_days) < int(minimum_days):
        return int(invalid_fallback_days)
    return int(max_days)


