# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ...animations.chart_policy import local_chart_animation_batch

DEFAULT_FSRS_FILTER_IDX = 2
FSRS_FILTER_MODES = ("1_month", "50_percent", "95_percent", "all")
FSRS_FILTER_LABELS_SHORT = ("1m", "50%", "95%", "all")
FSRS_FILTER_LABELS_LONG = ("1 month", "50%", "95%", "all")


# The four radio buttons can be changed per chart (Stability and Review Intervals).
# Modes: "d<N>" and "1_month" cap the axis at N days, "<N>_percent" / "p<N>" cap it at
# that share of the cards, "all" shows everything. Order here is the display order.
FSRS_FILTER_CHOICES = (
    ("d7", "1 week", "1w"),
    ("d14", "2 weeks", "2w"),
    ("1_month", "1 month", "1m"),
    ("d90", "3 months", "3m"),
    ("d365", "1 year", "1y"),
    ("50_percent", "50%", "50%"),
    ("p80", "80%", "80%"),
    ("p90", "90%", "90%"),
    ("95_percent", "95%", "95%"),
    ("p99", "99%", "99%"),
    ("all", "all", "all"),
)
_FSRS_PRESET_MODES = {m for m, _l, _s in FSRS_FILTER_CHOICES}
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
            return long_, short
    kind, n = parse_fsrs_mode(mode)
    return (f"{n} days", f"{n}d") if kind == "days" else (f"{n}%", f"{n}%")


def normalize_fsrs_filter_modes(modes):
    """Four distinct valid modes in display order; anything unusable gives the defaults."""
    try:
        values = [str(m) for m in (modes or [])]
    except Exception:
        return FSRS_FILTER_MODES
    values = [canonical_fsrs_mode(m) for m in values]
    if len(values) != 4 or len(set(values)) != 4 or any(parse_fsrs_mode(m) is None for m in values):
        return FSRS_FILTER_MODES
    return tuple(sorted(values, key=_fsrs_mode_sort_key))


def resolve_fsrs_filters(modes=None):
    """Return (modes, short_labels, long_labels) for the four radio buttons."""
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


def get_chart_fsrs_filter_mode(chart):
    for attr in ("filter_mode", "last_filter_mode"):
        value = getattr(chart, attr, None)
        if value is not None:
            return str(value)
    return None


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


def create_fsrs_filter_group(
    chart,
    *,
    labels,
    resolved_idx,
    make_radio_group,
    parent=None,
    on_idx_applied=None,
    default_idx=DEFAULT_FSRS_FILTER_IDX,
    modes=FSRS_FILTER_MODES,
):
    def _on_filter_change(idx):
        next_mode = get_fsrs_filter_mode(idx, default_idx=default_idx, modes=modes)
        if get_chart_fsrs_filter_mode(chart) == next_mode:
            return
        with local_chart_animation_batch(chart):
            chart.set_view_filter(next_mode, transition_mode="timespan")
        if callable(on_idx_applied):
            on_idx_applied(idx)

    return make_radio_group(list(labels), resolved_idx, _on_filter_change, parent)
