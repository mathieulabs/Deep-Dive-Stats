# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ....chart_utils import ChartGeometry, get_theme_colors
from ....chart_utils.tooltip import show_floating_label_at_y


def get_plot_geometry(widget):
    margin_left, margin_right = widget._get_margins()
    plot_width = widget.width() - margin_left - margin_right

    show_stats = getattr(widget, "show_stats", False)
    if show_stats:
        stats = widget.get_stats_text()
        margin_bottom = ChartGeometry.calculate_stats_margin(stats, plot_width, widget.fontMetrics())
    else:
        margin_bottom = ChartGeometry.MARGIN_BOTTOM

    margin_top = ChartGeometry.MARGIN_TOP
    plot_height = widget.height() - margin_top - margin_bottom
    return {
        "margin_left": margin_left,
        "margin_right": margin_right,
        "margin_top": margin_top,
        "margin_bottom": margin_bottom,
        "plot_width": plot_width,
        "plot_height": plot_height,
    }


def resolve_hover_index(x_local, plot_width, count):
    if count <= 0:
        return -1
    if x_local < 0:
        return 0
    if x_local >= plot_width:
        return count - 1
    idx = int((x_local / plot_width) * count)
    if idx < 0:
        return 0
    if idx >= count:
        return count - 1
    return idx


def update_avg_hover_state(
    widget,
    *,
    avg_value,
    max_val,
    margin_top,
    plot_height,
    mouse_y,
    in_plot_x,
    in_plot_y,
):
    was_hovering = widget.hover_avg
    widget.hover_avg = False
    y_avg = None

    if avg_value > 0 and max_val > 0 and in_plot_x and in_plot_y:
        y_avg = margin_top + plot_height - (avg_value / max_val * plot_height)
        threshold = 14 if was_hovering else 10
        if abs(mouse_y - y_avg) < threshold:
            widget.hover_avg = True

    return was_hovering, y_avg


def refresh_avg_hover_tooltip(widget, *, avg_value, y_avg, anchor_x_local):
    if widget.hover_avg and y_avg is not None:
        avg_text = f"Avg: {widget._format_metric_value(avg_value, compact=False)}"
        theme_colors = get_theme_colors(widget)
        text_color = (
            theme_colors.get("total_line")
            or theme_colors.get("text_primary")
            or theme_colors.get("text")
        )
        show_floating_label_at_y(
            widget,
            widget.avg_tooltip,
            text=avg_text,
            y_local=y_avg,
            anchor_x_local=anchor_x_local,
            theme_colors=theme_colors,
            text_color=text_color,
            show_only_if_hidden=True,
        )
    else:
        widget.avg_tooltip.hide()
