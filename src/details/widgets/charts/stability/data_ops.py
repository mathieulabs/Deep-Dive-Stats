# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QColor

from ...chart_utils.binning import get_bin_size
from ...chart_utils.formatting import fmt_num
from ...chart_utils.geometry import ChartGeometry
from ...common.fsrs_filters import (
    compute_fsrs_distribution_percentiles,
    resolve_fsrs_filter_max_days,
)
from ..common.discrete import (
    apply_discrete_transition_update,
    current_discrete_values_snapshot_impl,
    discrete_transition_target_unchanged,
    reset_discrete_transition_state,
    set_cumulative_mode_impl,
)
from ..fsrs_base import FSRSBaseChart


def init_state_impl(widget):
    widget.bottom_text_lines = 2
    widget.cumulative_visible = True
    widget.show_cumulative_axis = True
    widget.max_days = 31
    widget.last_filter_mode = "95_percent"
    widget._display_values = []
    widget._display_bin_size = 1
    widget._display_bins_count = 0
    reset_discrete_transition_state(widget, count_attr="bins_count")
    widget._view_initialized = False


def get_margins_impl(widget):
    ml, mr, _, mt = FSRSBaseChart._get_margins(widget)
    return ml, mr, ChartGeometry.MARGIN_BOTTOM, mt


def compute_median_impl(widget):
    percentile_data = compute_fsrs_distribution_percentiles(
        widget.data_dict or {},
        percentiles=(0.50,),
        positive_only=False,
        default_value=0,
    )
    widget.median = int(percentile_data["values"].get(0.50, 0))


def refresh_data_colors_impl(widget):
    from ....ui import Config, get_chart_color

    widget.color = QColor(get_chart_color(Config.COLOR_BAR, widget))


def update_data_impl(widget, new_data_dict, adaptive_binning=None, transition_mode=None):
    if adaptive_binning is not None:
        widget.adaptive_binning = adaptive_binning
    widget.data_dict = new_data_dict or {}
    widget._compute_median()
    widget.set_view_filter(widget.last_filter_mode, transition_mode=transition_mode)
    widget.maybe_start_initial_animation()


def build_binned_values_impl(widget, dist, max_days):
    bs = get_bin_size(max_days) if widget.binning_active else 1
    if bs <= 1:
        n_bins = max_days
    else:
        n_bins = (max_days // bs) + 1
    values = [0.0] * max(0, int(n_bins))
    if bs <= 1:
        for day, count in dist.items():
            idx = int(day) - 1
            if 0 <= idx < n_bins:
                values[idx] += float(count or 0.0)
    else:
        for day, count in dist.items():
            idx = int(day) // bs
            if 0 <= idx < n_bins:
                values[idx] += float(count or 0.0)
    return bs, n_bins, values


def current_values_snapshot_impl(widget):
    return current_discrete_values_snapshot_impl(widget)


def set_view_filter_impl(widget, filter_mode, transition_mode=None):
    is_initial_setup = not bool(getattr(widget, "_view_initialized", False))
    old_values = [float(v or 0.0) for v in (widget._display_values or [])]
    old_bins_count = int(widget._display_bins_count or len(old_values))
    old_max = max(1.0, float(widget.max_val or 0.0))

    widget.last_filter_mode = filter_mode
    dist = widget.data_dict or {}
    percentile_data = compute_fsrs_distribution_percentiles(
        dist,
        percentiles=(0.50, 0.95),
        positive_only=False,
        default_value=30,
    )
    p50 = int(percentile_data["values"].get(0.50, 30))
    p95 = int(percentile_data["values"].get(0.95, 30))

    max_days = resolve_fsrs_filter_max_days(
        filter_mode,
        dist=dist,
        p50=p50,
        p95=p95,
        one_month_days=31,
        all_fallback_days=30,
        invalid_fallback_days=1,
        minimum_days=1,
        positive_only=False,
    )

    widget.max_days = max_days
    filtered_dist = {k: v for k, v in dist.items() if k <= max_days}
    bs, n_bins, values = widget._build_binned_values(filtered_dist, max_days)
    widget._display_bin_size = max(1, int(bs))
    widget._display_bins_count = max(0, int(n_bins))
    widget._display_values = [float(v or 0.0) for v in values]
    # Without grouping, bin i holds day i + 1. With grouping, bin i starts at day i * size.
    first_day = 1 if widget._display_bin_size <= 1 else 0
    widget.data_list = [(i * widget._display_bin_size + first_day, v) for i, v in enumerate(widget._display_values)]
    widget.total_cards = int(sum(widget._display_values))
    widget.max_val = max(widget._display_values) if widget._display_values and max(widget._display_values) > 0 else 1

    new_values = [float(v or 0.0) for v in widget._display_values]
    new_bins_count = int(widget._display_bins_count or 0)
    new_max = max(new_values) if new_values and max(new_values) > 0 else 1.0
    widget._transition_align_right = False
    target_unchanged_while_running = discrete_transition_target_unchanged(
        widget,
        new_points_count=new_bins_count,
        new_values=new_values,
        count_attr="bins_count",
    )
    if target_unchanged_while_running:
        widget.hover_index = -1
        widget.update()
        return

    if is_initial_setup:
        reset_discrete_transition_state(widget, count_attr="bins_count")
        widget._view_initialized = True
    elif apply_discrete_transition_update(
        widget,
        old_values=old_values,
        new_values=new_values,
        old_max=old_max,
        new_max=new_max,
        old_count=old_bins_count,
        new_count=new_bins_count,
        count_attr="bins_count",
        align_right=False,
    ):
        pass
    else:
        reset_discrete_transition_state(widget, count_attr="bins_count")

    widget.hover_index = -1
    widget.update()


def get_stats_text_impl(widget):
    return [f"Total: {fmt_num(widget.total_cards)} cards", f"Median stability: {widget.median} days"]


def get_tooltip_text_impl(widget, k, v):
    bs = get_bin_size(widget.max_days) if widget.binning_active else 1
    if bs <= 1:
        return f"Stability {k} days: {v} cards"
    return f"Stability {k}-{k + bs - 1} days: {v} cards"
