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
    min_day = widget._get_min_day_for_dist(dist, show_backlog)
    points_count = widget._get_points_count_for_dist(dist, max_days, show_backlog)
    values = []
    for i in range(points_count):
        day, next_day = widget._get_bin_day_range_for(i, points_count, min_day, max_days)
        values.append(sum(float(dist.get(d, 0) or 0.0) for d in range(day, next_day)))
    return points_count, values


def refresh_data_colors_impl(widget):
    from ....ui import Config, get_chart_color
    widget.bar_color = QColor(get_chart_color(Config.COLOR_FUTURE_DUE, widget))


def update_data_impl(widget, new_data, adaptive_binning=None, transition_mode=None):
    if adaptive_binning is not None:
        widget.adaptive_binning = adaptive_binning
    old_dist = dict(widget.data_dict.get("distribution", {}) or {})

    old_values = [float(v or 0.0) for v in (widget._display_values or [])]
    old_points_count = int(widget._points_count or len(old_values))
    old_max = max(1.0, float(widget.max_val or 0.0))

    def _has_backlog(dist):
        if not widget.show_backlog:
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

    backlog_presence_changed = _has_backlog(old_dist) != _has_backlog(dist)
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


def get_tooltip_text_impl(widget, idx, points_count):
    dist = widget.data_dict.get("distribution", {})
    day, next_day = widget._get_bin_day_range(idx, points_count)
    bucket_sum = sum(dist.get(d, 0) for d in range(day, next_day))
    if next_day - day > 1:
        if day < 0 and next_day <= 0:
            return f"{abs(day)}-{abs(next_day-1)} days ago: {fmt_num(bucket_sum)} reviews"
        return f"Days {day}-{next_day-1}: {fmt_num(bucket_sum)} reviews"
    if day == -1:
        return f"Yesterday: {fmt_num(bucket_sum)} reviews"
    if day < -1:
        return f"{abs(day)} days ago: {fmt_num(bucket_sum)} reviews"
    if day == 0:
        return f"Today: {fmt_num(bucket_sum)} reviews"
    return f"Day {day}: {fmt_num(bucket_sum)} reviews"


def get_stats_text_impl(widget):
    total = widget.data_dict.get("total", 0)
    avg = widget.data_dict.get("average", 0)
    tomorrow = widget.data_dict.get("tomorrow", 0)
    backlog = widget.data_dict.get("backlog", 0)
    stats = [
        f"Total: {fmt_num_compact(total)} reviews",
        f"Average: {fmt_num_compact(avg)} reviews/day",
        f"Due tomorrow: {fmt_num_compact(tomorrow)} reviews",
    ]
    if widget.show_backlog and backlog > 0:
        stats.append(f"Backlog: {fmt_num_compact(backlog)} overdue")
    return stats
