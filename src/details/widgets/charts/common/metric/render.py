# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ....chart_utils import ChartGeometry


def calculate_stats_margin(widget, painter, plot_width):
    show_stats = getattr(widget, "show_stats", False)
    if show_stats:
        stats = widget.get_stats_text()
        return ChartGeometry.calculate_stats_margin(stats, plot_width, painter.fontMetrics())
    return ChartGeometry.MARGIN_BOTTOM


def compute_transition_presence(widget, t, *, relative_transition=False):
    if relative_transition:
        return 1.0
    if widget._global_transition_mode == "from_empty":
        return t
    if widget._global_transition_mode == "to_empty":
        return 1.0 - t
    if widget._data_transition_active:
        return 1.0
    return widget._progress


def interpolate_axis_max(old_values, new_values, t):
    old_max = max(old_values) if old_values else 0.0
    new_max = max(new_values) if new_values else 0.0
    # Same floor as the static paint path (max 0 -> 1) at both ends, so a
    # transition into/out of an empty series doesn't end on a 0/0/0 axis.
    if old_max <= 0:
        old_max = 1.0
    if new_max <= 0:
        new_max = 1.0
    lo, hi = min(old_max, new_max), max(old_max, new_max)
    if lo > 0 and hi / lo > 3.0:
        # Big scale change (30 daily bars to the whole history): ease the axis in log
        # space so it does not snap to the end value and flatten the bars.
        import math

        axis_max = math.exp(math.log(old_max) + ((math.log(new_max) - math.log(old_max)) * t))
    else:
        axis_max = old_max + ((new_max - old_max) * t)
    if axis_max < 0:
        axis_max = 0.0
    return axis_max


def calculate_margin_pair(font_metrics, values, cumulative_visible, *, value_formatter=None):
    values = values or []
    safe_max = max(values) if values else 1.0
    if safe_max <= 0:
        safe_max = 1.0
    left = ChartGeometry.calculate_dynamic_left_margin(
        font_metrics,
        safe_max,
        value_formatter=value_formatter,
    )
    right = ChartGeometry.calculate_dynamic_right_margin(
        font_metrics,
        values,
        cumulative_visible,
        value_formatter=value_formatter,
    )
    return left, right


def interpolate_margin_pair(
    font_metrics,
    old_values,
    new_values,
    t,
    cumulative_visible,
    *,
    old_formatter=None,
    new_formatter=None,
):
    old_left, old_right = calculate_margin_pair(
        font_metrics,
        old_values,
        cumulative_visible,
        value_formatter=old_formatter,
    )
    new_left, new_right = calculate_margin_pair(
        font_metrics,
        new_values,
        cumulative_visible,
        value_formatter=new_formatter,
    )
    left = int(round(old_left + ((new_left - old_left) * t)))
    right = int(round(old_right + ((new_right - old_right) * t)))
    return left, right


def split_transition_labels(old_rows, new_rows, *, label_getter):
    old_labels = [str(label_getter(item) or "") for item in (old_rows or [])]
    new_labels = [str(label_getter(item) or "") for item in (new_rows or [])]
    axis_old_labels = [label.split(" - ")[0] for label in old_labels]
    axis_new_labels = [label.split(" - ")[0] for label in new_labels]
    return axis_old_labels, axis_new_labels
