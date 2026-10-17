# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QColor

from ...chart_utils.binning import get_bin_size
from ...chart_utils.formatting import fmt_num
from ...common.fsrs_filters import (
    compute_fsrs_distribution_percentiles,
    resolve_fsrs_filter_max_days,
)
from ..common.discrete import (
    apply_discrete_transition_update,
    binning_active_getter,
    current_discrete_values_snapshot_impl,
    discrete_transition_target_unchanged,
    reset_discrete_transition_state,
    set_chart_opacity_impl,
    set_cumulative_mode_impl,
)


def invalidate_data_caches_impl(widget):
    widget._binned_data_cache = None
    widget._path_cache = {}
    if hasattr(widget, "_calc_averages"):
        widget._calc_averages()


def get_points_count_impl(widget):
    return widget._points_count


def day_range_impl(widget, i, points_count):
    day = 1 + int(i * widget.max_days / points_count)
    next_day = 1 + int((i + 1) * widget.max_days / points_count)
    return day, next_day


def build_display_values_impl(widget, dist, max_days):
    if not widget.binning_active:
        points_count = max_days
    else:
        bs = get_bin_size(max_days)
        if bs <= 1:
            points_count = max_days
        else:
            points_count = max(1, max_days // bs)
    values = []
    for i in range(points_count):
        day, next_day = widget._day_range(i, points_count)
        bucket_sum = 0.0
        for d in range(day, next_day):
            bucket_sum += float(dist.get(d, 0) or 0.0)
        values.append(bucket_sum)
    return points_count, values


def current_values_snapshot_impl(widget):
    return current_discrete_values_snapshot_impl(widget)


def set_view_filter_impl(widget, filter_mode, transition_mode=None):
    is_initial_setup = not bool(getattr(widget, "_view_initialized", False))
    force_instant_commit = transition_mode == "instant"
    old_values = [float(v or 0.0) for v in (widget._display_values or [])]
    old_points_count = int(widget._points_count or len(old_values))
    old_max = max(1.0, float(widget.max_val or 0.0))

    widget.filter_mode = filter_mode
    dist = widget.data_dict.get("distribution", {})
    widget.max_days = resolve_fsrs_filter_max_days(
        filter_mode,
        dist=dist,
        p50=getattr(widget, "p50", 30),
        p95=getattr(widget, "p95", 30),
        one_month_days=31,
        all_fallback_days=30,
        invalid_fallback_days=31,
        minimum_days=1,
    )

    widget.filtered_dist = {k: v for k, v in dist.items() if 0 < k <= widget.max_days}
    widget._points_count, widget._display_values = widget._build_display_values(widget.filtered_dist, widget.max_days)
    widget.max_val = max(widget._display_values) if widget._display_values and max(widget._display_values) > 0 else 1

    new_values = [float(v or 0.0) for v in widget._display_values]
    new_points_count = int(widget._points_count or 0)
    new_max = max(new_values) if new_values and max(new_values) > 0 else 1.0

    widget._transition_align_right = False
    target_unchanged_while_running = discrete_transition_target_unchanged(
        widget,
        new_points_count=new_points_count,
        new_values=new_values,
    )
    if target_unchanged_while_running:
        widget._clear_hover()
        widget.update()
        return

    if is_initial_setup or force_instant_commit:
        reset_discrete_transition_state(widget)
        widget._view_initialized = True
    else:
        apply_discrete_transition_update(
            widget,
            old_values=old_values,
            new_values=new_values,
            old_max=old_max,
            new_max=new_max,
            old_count=old_points_count,
            new_count=new_points_count,
            count_attr="points_count",
            align_right=False,
        )

    widget._clear_hover()
    widget.update()


def refresh_data_colors_impl(widget):
    from ....ui import Config, get_chart_color
    widget.bar_color = QColor(get_chart_color(Config.COLOR_BAR, widget))


def update_data_impl(widget, new_data, adaptive_binning=None, transition_mode=None):
    if adaptive_binning is not None:
        widget.adaptive_binning = adaptive_binning
    widget.data_dict = new_data
    widget._compute_stats()
    widget.set_view_filter(widget.filter_mode, transition_mode=transition_mode)
    widget.maybe_start_initial_animation()


def get_tooltip_text_impl(widget, idx, points_count):
    day, next_day = widget._day_range(idx, points_count)
    bucket_sum = 0
    for d in range(day, next_day):
        bucket_sum += widget.filtered_dist.get(d, 0)
    if next_day - day > 1:
        return f"Interval {day}-{next_day-1} days: {fmt_num(bucket_sum)} cards"
    return f"Interval {day} days: {fmt_num(bucket_sum)} cards"


def compute_stats_impl(widget):
    widget.stats_median = 0
    widget.p50 = widget.data_dict.get("p50", 31)
    widget.p95 = widget.data_dict.get("p95", 365)
    dist = widget.data_dict.get("distribution", {})
    percentile_data = compute_fsrs_distribution_percentiles(
        dist,
        percentiles=(0.50, 0.95),
        positive_only=True,
        default_value=30,
    )
    widget.stats_total = percentile_data["total"]
    widget.p50 = int(percentile_data["values"].get(0.50, widget.p50))
    widget.p95 = int(percentile_data["values"].get(0.95, widget.p95))
    if widget.stats_total > 0:
        widget.stats_median = widget.p50


def get_stats_text_impl(widget):
    return [f"Median interval: {widget.stats_median} days"]
