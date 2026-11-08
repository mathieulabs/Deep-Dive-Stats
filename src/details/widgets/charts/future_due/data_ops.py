# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QColor

from ...chart_utils.binning import get_bin_size
from ...chart_utils.formatting import fmt_num, fmt_num_compact
from ..common.discrete import (
    apply_discrete_transition_update,
    binning_active_getter,
    discrete_transition_target_unchanged,
    set_chart_opacity_impl,
    set_cumulative_mode_impl,
)
from .....i18n import N_, percent_text, tr, tr_n, tr_name


def get_min_day_impl(widget):
    dist = widget.data_dict.get("distribution", {})
    # Called once per bar on every paint, so scanning the distribution each time is costly.
    key = (id(dist), len(dist or ()), bool(widget.show_backlog))
    cached = getattr(widget, "_min_day_cache", None)
    if cached is not None and cached[0] == key:
        return cached[1]
    value = widget._get_min_day_for_dist(dist, widget.show_backlog)
    widget._min_day_cache = (key, value)
    return value


def get_min_day_for_dist_impl(widget, dist, show_backlog):
    if not show_backlog:
        return 0
    neg_keys = [k for k, v in (dist or {}).items() if k < 0 and float(v or 0.0) > 0.0]
    return min(neg_keys) if neg_keys else 0


def update_max_val_impl(widget):
    dist = widget.data_dict.get("distribution", {})
    points_count = widget._get_points_count()
    if not dist or points_count <= 0:
        # Empty deck: integer axis (0..4) instead of 0, 0.2, 0.5, 0.8, 1.
        widget.max_val = 4
        return
    current_max = 0
    for i in range(points_count):
        day, next_day = widget._get_bin_day_range(i, points_count)
        bucket_sum = sum(dist.get(d, 0) for d in range(day, next_day))
        current_max = max(current_max, bucket_sum)
    if current_max > 0 and widget.percent_active():
        current_max = 100.0  # the bars are shares
    widget.max_val = current_max if current_max > 0 else 1


def get_bin_day_range_impl(widget, idx, points_count):
    return widget._get_bin_day_range_for(idx, points_count, widget._get_min_day(), widget.max_days)


def get_bin_day_range_for_impl(widget, idx, points_count, min_day, max_days):
    total_span = max_days - min_day
    if not widget.binning_active or min_day >= 0:
        day = min_day + int(idx * (total_span + 1) / points_count)
        next_day = min_day + int((idx + 1) * (total_span + 1) / points_count)
        return day, next_day

    backlog_span = abs(min_day)
    future_span = max_days
    bs_back = get_bin_size(backlog_span)
    backlog_buckets = max(1, backlog_span // max(1, bs_back))
    if idx < backlog_buckets:
        d_start = min_day + int(idx * backlog_span / backlog_buckets)
        d_end = min_day + int((idx + 1) * backlog_span / backlog_buckets)
        return d_start, min(0, d_end)
    f_idx = idx - backlog_buckets
    future_buckets = points_count - backlog_buckets
    if future_buckets <= 0:
        return 0, max_days + 1
    d_start = int(f_idx * (future_span + 1) / future_buckets)
    d_end = int((f_idx + 1) * (future_span + 1) / future_buckets)
    return max(0, d_start), d_end


def invalidate_data_caches_impl(widget):
    widget._update_max_val()


def get_points_count_impl(widget):
    dist = widget.data_dict.get("distribution", {})
    return widget._get_points_count_for_dist(dist, widget.max_days, widget.show_backlog)


def get_points_count_for_dist_impl(widget, dist, max_days, show_backlog):
    min_day = widget._get_min_day_for_dist(dist, show_backlog)
    total_span = max_days - min_day
    if not widget.binning_active:
        return total_span + 1
    bs = get_bin_size(total_span)
    if bs <= 1:
        return total_span + 1
    if min_day < 0:
        backlog_span = abs(min_day)
        future_span = max_days
        bs_back = get_bin_size(backlog_span)
        bs_future = get_bin_size(future_span)
        backlog_buckets = max(1, backlog_span // max(1, bs_back))
        future_buckets = max(1, (future_span + 1) // max(1, bs_future))
        return backlog_buckets + future_buckets
    return max(1, (total_span + 1) // bs)


def build_display_values_impl(widget, dist, max_days, show_backlog):
    widget._built_backlog = bool(show_backlog)  # the backlog setting of the bars shown
    min_day = widget._get_min_day_for_dist(dist, show_backlog)
    points_count = widget._get_points_count_for_dist(dist, max_days, show_backlog)
    values = []
    for i in range(points_count):
        day, next_day = widget._get_bin_day_range_for(i, points_count, min_day, max_days)
        values.append(sum(float(dist.get(d, 0) or 0.0) for d in range(day, next_day)))
    if widget.percent_active():
        values = [100.0 if v > 0 else 0.0 for v in values]  # "Show as %": full bars
    return points_count, values


def refresh_data_colors_impl(widget):
    from ....ui import Config, get_chart_color
    widget.bar_color = QColor(get_chart_color(Config.COLOR_FUTURE_DUE, widget))


def breakdown_parts(kind):
    """The parts of a breakdown, bottom to top: (tooltip id, label, colour key)."""
    from ....ui import Config

    if kind == "result":
        return (
            ("pass", N_("Predicted pass"), Config.COLOR_GOOD),
            ("fail", N_("Predicted fail"), Config.COLOR_AGAIN),
            ("no_fsrs", N_("No FSRS data"), Config.COLOR_FUTURE_DUE),
        )
    return (
        ("mature", N_("Mature"), Config.COLOR_MATURE),
        ("young", N_("Young"), Config.COLOR_YOUNG),
        ("learn", N_("Learning"), Config.COLOR_LEARN),
    )


def _bin_parts(days, day, next_day):
    sums = [0.0, 0.0, 0.0]
    for d in range(day, next_day):
        c3 = days.get(d)
        if c3:
            for k in range(3):
                sums[k] += c3[k]
    return sums


def type_shares(widget, data, dist, max_days, count):
    """Breakdown: (kind, each bar's shares of its three parts bottom to top), a share of
    (0, 0, 0) for a bar without cards; None without a breakdown (plain bars). Kept for the
    old and the new data so the parts glide during a transition, as the bars do."""
    bd = (data or {}).get("breakdown")
    if not bd or not bd.get("days"):
        return None
    days = bd["days"]
    min_day = widget._get_min_day_for_dist(dist, widget.show_backlog)
    out = []
    for i in range(int(count or 0)):
        sums = _bin_parts(days, *widget._get_bin_day_range_for(i, count, min_day, max_days))
        total = float(sum(sums))
        out.append(tuple(v / total for v in sums) if total > 0 else (0.0, 0.0, 0.0))
    return bd.get("kind"), out


def update_data_impl(widget, new_data, adaptive_binning=None, transition_mode=None):
    if adaptive_binning is not None:
        widget.adaptive_binning = adaptive_binning
    old_dist = dict(widget.data_dict.get("distribution", {}) or {})

    old_values = [float(v or 0.0) for v in (widget._display_values or [])]
    old_points_count = int(widget._points_count or len(old_values))
    old_max = max(1.0, float(widget.max_val or 0.0))

    def _backlog_flags(dist, max_days, count):
        """Which bars are backlog (overdue) bars, to fade their colour during a transition."""
        min_day = widget._get_min_day_for_dist(dist, widget.show_backlog)
        if min_day >= 0:
            return [False] * int(count or 0)
        return [widget._get_bin_day_range_for(i, count, min_day, max_days)[0] < 0 for i in range(int(count or 0))]

    # The old bars as they are shown: the caller may already have switched the backlog on or
    # off (show_backlog) before this update, which placed the old parts and colours on the
    # wrong bars (the mature parts then appeared at once when toggling Backlog).
    new_backlog = widget.show_backlog
    old_backlog = bool(getattr(widget, "_built_backlog", new_backlog))
    widget.show_backlog = old_backlog
    try:
        old_flags = _backlog_flags(old_dist, widget.max_days, old_points_count)
        old_shares = type_shares(widget, widget.data_dict, old_dist, widget.max_days, old_points_count)
    finally:
        widget.show_backlog = new_backlog

    def _has_backlog(dist, shown=None):
        if not (widget.show_backlog if shown is None else shown):
            return False
        return any((int(k) < 0 and float(v or 0.0) > 0.0) for k, v in (dist or {}).items())

    widget.data_dict = new_data
    widget.max_days = widget.data_dict.get("max_days", 31)
    dist = widget.data_dict.get("distribution", {})
    widget._points_count, widget._display_values = widget._build_display_values(dist, widget.max_days, widget.show_backlog)
    widget._update_max_val()
    new_values = [float(v or 0.0) for v in (widget._display_values or [])]
    new_points_count = int(widget._points_count or len(new_values))
    new_max = max(new_values) if new_values and max(new_values) > 0 else 1.0
    widget._backlog_flags = (old_flags, _backlog_flags(dist, widget.max_days, new_points_count))
    widget._type_shares = (old_shares, type_shares(widget, widget.data_dict, dist, widget.max_days, new_points_count))

    backlog_presence_changed = _has_backlog(old_dist, old_backlog) != _has_backlog(dist)
    effective_transition_mode = transition_mode
    if effective_transition_mode is None and backlog_presence_changed:
        effective_transition_mode = "timespan"

    widget._transition_align_right = (effective_transition_mode == "timespan")
    target_unchanged_while_running = discrete_transition_target_unchanged(
        widget,
        new_points_count=new_points_count,
        new_values=new_values,
    )
    if target_unchanged_while_running:
        widget._clear_hover()
        widget.maybe_start_initial_animation()
        widget.update()
        return

    animate_kwargs = None
    if effective_transition_mode == "timespan":
        animate_kwargs = {
            "min_duration_ms": 220,
            "max_duration_ms": 280,
            "empty_transition_duration_ms": 240,
        }
    apply_discrete_transition_update(
        widget,
        old_values=old_values,
        new_values=new_values,
        old_max=old_max,
        new_max=new_max,
        old_count=old_points_count,
        new_count=new_points_count,
        count_attr="points_count",
        align_right=(effective_transition_mode == "timespan"),
        animate_kwargs=animate_kwargs,
    )

    widget._clear_hover()
    widget.maybe_start_initial_animation()
    widget.update()


def _running_total(widget, idx, points_count):
    dist = widget.data_dict.get("distribution", {})
    first, _ = widget._get_bin_day_range(0, points_count)
    _day, next_day = widget._get_bin_day_range(idx, points_count)
    return sum(dist.get(d, 0) for d in range(first, next_day))


def _bin_label(day, next_day):
    if next_day - day > 1:
        if day < 0 and next_day <= 0:
            return tr("{start}-{end} days ago", start=abs(day), end=abs(next_day - 1))
        return tr("Days {start}-{end}", start=day, end=next_day - 1)
    if day == -1:
        return tr("Yesterday")
    if day < -1:
        return tr("{days} days ago", days=abs(day))
    if day == 0:
        return tr("Today")
    return tr("Day {day}", day=day)


def _breakdown_tooltip_lines(widget, idx, points_count, bd):
    """With a breakdown: the tooltip of Activity's breakdown (the days and their cards as
    header, a coloured line per part, top part first, then the running total)."""
    from ....ui import get_chart_color

    day, next_day = widget._get_bin_day_range(idx, points_count)
    sums = _bin_parts(bd.get("days") or {}, day, next_day)
    dist = widget.data_dict.get("distribution", {})
    total = sum(dist.get(d, 0) for d in range(day, next_day))
    lines = [{"text": _bin_label(day, next_day), "header": True,
              "value": tr_n("{count} card", "{count} cards", total, count=fmt_num(total)) if total else ""}]
    for (key, label, color), n in reversed(list(zip(breakdown_parts(bd.get("kind")), sums))):
        if n >= 0.05:
            value = fmt_num(n) if float(n).is_integer() else fmt_num(n, 1)
            if widget.percent_active() and sum(sums) > 0:
                value = f"{percent_text(fmt_num(n * 100.0 / sum(sums), 1))} ({value})"
            lines.append({"id": key, "text": tr_name(label), "value": value,
                          "color": QColor(get_chart_color(color, widget)).name()})
    if bd.get("kind") == "result" and (sums[0] + sums[1]) > 0:
        r = sums[0] / (sums[0] + sums[1])
        lines.append({"id": "retention", "text": tr("Expected retention"), "value": percent_text(fmt_num(r * 100.0, 1))})
    if getattr(widget, "cumulative_visible", True):
        running = _running_total(widget, idx, points_count)
        lines.append({"id": "total", "text": tr("Total: {value}", value=fmt_num(running)), "bold": True})
    return lines


def get_tooltip_text_impl(widget, idx, points_count):
    """Text of a bar's tooltip, or its lines (dicts) with a breakdown."""
    bd = widget.data_dict.get("breakdown")
    if bd and bd.get("days"):
        return _breakdown_tooltip_lines(widget, idx, points_count, bd)
    text = _bin_tooltip_line(widget, idx, points_count)
    if getattr(widget, "cumulative_visible", True) and "total" not in (getattr(widget, "tooltip_hidden", None) or ()):
        # The running total the cumulative curve shows at this bar.
        dist = widget.data_dict.get("distribution", {})
        first, _ = widget._get_bin_day_range(0, points_count)
        _day, next_day = widget._get_bin_day_range(idx, points_count)
        running = sum(dist.get(d, 0) for d in range(first, next_day))
        text += "\n" + tr_n("Total: {count} review", "Total: {count} reviews", running, count=fmt_num(running))
    return text


def _bin_tooltip_line(widget, idx, points_count):
    dist = widget.data_dict.get("distribution", {})
    day, next_day = widget._get_bin_day_range(idx, points_count)
    bucket_sum = sum(dist.get(d, 0) for d in range(day, next_day))
    reviews = tr_n("{count} review", "{count} reviews", bucket_sum, count=fmt_num(bucket_sum))
    if next_day - day > 1:
        if day < 0 and next_day <= 0:
            return tr("{start}-{end} days ago: {reviews}", start=abs(day), end=abs(next_day - 1), reviews=reviews)
        return tr("Days {start}-{end}: {reviews}", start=day, end=next_day - 1, reviews=reviews)
    if day == -1:
        return tr("Yesterday: {reviews}", reviews=reviews)
    if day < -1:
        return tr("{days} days ago: {reviews}", days=abs(day), reviews=reviews)
    if day == 0:
        return tr("Today: {reviews}", reviews=reviews)
    return tr("Day {day}: {reviews}", day=day, reviews=reviews)


def get_stats_text_impl(widget):
    total = widget.data_dict.get("total", 0)
    avg = widget.data_dict.get("average", 0)
    tomorrow = widget.data_dict.get("tomorrow", 0)
    backlog = widget.data_dict.get("backlog", 0)
    stats = [
        tr_n("Total: {count} review", "Total: {count} reviews", total, count=fmt_num_compact(total)),
        tr("Average: {count} reviews/day", count=fmt_num_compact(avg)),
        tr_n("Due tomorrow: {count} review", "Due tomorrow: {count} reviews", tomorrow, count=fmt_num_compact(tomorrow)),
    ]
    if widget.show_backlog and backlog > 0:
        stats.append(tr("Backlog: {count} overdue", count=fmt_num_compact(backlog)))
    ret = widget.data_dict.get("retention")
    bd = widget.data_dict.get("breakdown") or {}
    if ret and bd.get("kind") == "result":
        # Breakdown by Result: the expected retention of the cards due in the period shown.
        r_sum = n = 0
        for d, c2 in ret.items():
            if d >= 0 or widget.show_backlog:
                r_sum += c2[0]
                n += c2[1]
        if n:
            stats.append(tr("Expected retention: {value}", value=percent_text(fmt_num(r_sum / n * 100.0, 1))))
    return stats
