# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Cumulative total line and area shared by the Future Due and Review Intervals charts."""

from aqt.qt import QRectF
from . import build_cumulative_paths, build_cumulative_points, build_default_line_x_positions, build_running_total_series, resample_discrete_series
from ....chart_utils.drawing import draw_cumulative_line_and_area


def normalized_running_total(vals):
    out = build_running_total_series([max(0.0, float(vv or 0.0)) for vv in vals])
    end = out[-1] if out and out[-1] > 0 else 1.0
    return [v / end for v in out] if out else [0.0]


def draw_cumulative_area_impl(widget, painter, plot_w, plot_h, margin_left, margin_top, total_cards):
    draw_values = getattr(widget, "_anim_draw_values", widget._display_values)
    points_count = int(getattr(widget, "_anim_draw_points_count", widget._points_count) or 0)
    if points_count <= 0:
        return

    t = widget.get_progress()
    old_points = int(widget._transition_old_points_count or 0)
    new_points = int(widget._transition_new_points_count or 0)
    count_changed = widget._data_transition_active and old_points > 0 and new_points > 0 and old_points != new_points
    line_points = new_points if count_changed else points_count

    if widget._data_transition_active and widget._transition_align_right and (not count_changed):
        x_positions = widget.interpolate_line_x_positions(
            widget._transition_old_points_count,
            widget._transition_new_points_count,
            t,
            margin_left,
            plot_w,
            align_right=True,
        )
    else:
        x_positions = build_default_line_x_positions(margin_left, plot_w, line_points)

    if widget._data_transition_active:
        line_t = t
        if count_changed and line_t >= 0.98:
            line_t = 1.0
        old_vals = [float(v or 0.0) for v in (widget._transition_old_values or [])]
        new_vals = [float(v or 0.0) for v in (widget._transition_new_values or [])]
        sample_n = max(1, len(x_positions))

        old_curve = resample_discrete_series(normalized_running_total(old_vals), sample_n)
        new_curve = resample_discrete_series(normalized_running_total(new_vals), sample_n)
        cumulative_draw_values = [widget.interpolate_scalar(old_curve[i], new_curve[i], line_t) for i in range(sample_n)]
        line_total = 1.0
    else:
        cumulative_draw_values = build_running_total_series(draw_values)
        line_total = total_cards if total_cards > 0 else 1.0

    points = build_cumulative_points(
        x_positions,
        cumulative_draw_values,
        margin_top=margin_top,
        plot_h=plot_h,
        line_total=line_total,
    )
    path, fill_path = build_cumulative_paths(points, margin_top=margin_top, plot_h=plot_h)
    if not path or not fill_path:
        return

    painter.save()
    painter.setClipRect(QRectF(margin_left, margin_top - 2.0, plot_w, plot_h + 2.0))
    draw_cumulative_line_and_area(painter, path, fill_path, widget=widget)
    painter.restore()
