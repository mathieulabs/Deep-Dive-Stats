# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QPainter

from ...chart_utils.geometry import ChartGeometry
from ..common.discrete import draw_cached_discrete_scaffold, finalize_discrete_transition_state


def paint_event_impl(widget, event):
    if not widget.data_list:
        return

    painter = QPainter(widget)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    w = widget.width()
    h = widget.height()

    t = widget.get_progress()
    if t >= 0.995:
        t = 1.0

    draw_values = [float(v or 0.0) for _, v in widget.data_list]
    axis_max = widget.max_val if widget.max_val > 0 else 1.0
    draw_ratios = [max(0.0, (v / max(1.0, axis_max))) for v in draw_values]
    if widget._data_transition_active:
        old_vals = widget._transition_old_values or []
        new_vals = widget._transition_new_values or []
        old_max = max(old_vals) if old_vals and max(old_vals) > 0 else 1.0
        new_max = max(new_vals) if new_vals and max(new_vals) > 0 else 1.0
        axis_max = max(1.0, old_max + ((new_max - old_max) * t))
        draw_values = widget.interpolate_numeric_series(old_vals, new_vals, t, align_right=False)
        n = max(len(old_vals), len(new_vals))
        old_pad = list(old_vals) + ([0.0] * (n - len(old_vals)))
        new_pad = list(new_vals) + ([0.0] * (n - len(new_vals)))
        draw_ratios = []
        for ov, nv in zip(old_pad, new_pad):
            r0 = max(0.0, ov / old_max)
            r1 = max(0.0, nv / new_max)
            draw_ratios.append(max(0.0, min(1.0, r0 + ((r1 - r0) * t))))
    else:
        intro = max(0.0, min(1.0, float(t)))
        if intro < 0.999:
            draw_ratios = [max(0.0, min(1.0, r * intro)) for r in draw_ratios]

    widget._anim_draw_values = draw_values
    widget._anim_draw_ratios = draw_ratios
    widget._anim_axis_max = axis_max

    margin_left = ChartGeometry.calculate_dynamic_left_margin(widget.fontMetrics(), axis_max)
    if widget.show_cumulative_axis:
        margin_right = ChartGeometry.calculate_dynamic_right_margin(widget.fontMetrics(), [widget.total_cards], True)
    else:
        margin_right = widget._non_cumulative_margin_right
    margin_top = ChartGeometry.MARGIN_TOP
    if widget._data_transition_active:
        old_left = ChartGeometry.calculate_dynamic_left_margin(widget.fontMetrics(), max(1.0, widget._transition_old_max))
        new_left = ChartGeometry.calculate_dynamic_left_margin(widget.fontMetrics(), max(1.0, widget._transition_new_max))
        margin_left = int(round(old_left + ((new_left - old_left) * t)))

    plot_w = w - margin_left - margin_right
    if widget.show_stats:
        stats = widget.get_stats_text()
        margin_bottom = ChartGeometry.calculate_stats_margin(stats, plot_w, painter.fontMetrics())
    else:
        margin_bottom = ChartGeometry.MARGIN_BOTTOM
    plot_h = h - margin_bottom - margin_top

    max_cum = widget.total_cards if widget.show_cumulative_axis else None
    draw_cached_discrete_scaffold(
        widget,
        painter,
        width=w,
        height=h,
        margin_left=margin_left,
        margin_top=margin_top,
        margin_right=margin_right,
        margin_bottom=margin_bottom,
        axis_max=axis_max,
        max_cumulative=max_cum,
    )

    widget.draw_bars(painter, plot_w, plot_h, margin_left, margin_top)
    widget.draw_extras(painter, plot_w, plot_h, margin_left, margin_top, margin_bottom, w, h)
    finalize_discrete_transition_state(widget, t=t)
