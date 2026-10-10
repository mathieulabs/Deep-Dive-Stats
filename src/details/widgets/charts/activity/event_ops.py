# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QWidget

from ...chart_utils import ChartGeometry
from ...chart_utils.tooltip import show_tooltip_near
from ..common.metric import (
    change_event_impl,
    get_plot_geometry,
    hide_event_impl,
    leave_event_impl,
    mouse_press_event_impl,
    mouse_release_event_impl,
    refresh_avg_hover_tooltip,
    reset_zoom_with_transition_impl,
    resize_event_impl,
    resolve_hover_index,
    set_zoom_range_impl,
    update_avg_hover_state,
)


def mouse_move_event_impl(widget, event):
    display_data = widget._get_display_data()
    if not display_data:
        return

    plot = get_plot_geometry(widget)
    width = plot["plot_width"]
    if width <= 0:
        return

    margin_left = plot["margin_left"]
    margin_top = plot["margin_top"]
    plot_h = plot["plot_height"]

    if widget.handle_selection_move(event, margin_left, width):
        return

    x = event.pos().x() - margin_left
    n = len(display_data)

    was_hover_index = widget.hover_index
    widget.hover_index = resolve_hover_index(x, width, n)

    values = widget._get_values()
    max_val = widget._get_max_val()

    mouse_y = event.pos().y()
    in_plot_x = 0 <= x < width
    in_plot_y = margin_top <= mouse_y <= (margin_top + plot_h)
    avg_val = 0
    if getattr(widget, "avg_visible", True) and values:
        avg_val = widget._get_averages()
    was_hovering_avg, y_avg = update_avg_hover_state(
        widget,
        avg_value=avg_val,
        max_val=max_val,
        margin_top=margin_top,
        plot_height=plot_h,
        mouse_y=mouse_y,
        in_plot_x=in_plot_x,
        in_plot_y=in_plot_y,
    )

    if widget.hover_avg != was_hovering_avg or widget.hover_index != was_hover_index:
        widget.update()

    refresh_avg_hover_tooltip(
        widget,
        avg_value=avg_val,
        y_avg=y_avg,
        anchor_x_local=ChartGeometry.calculate_dynamic_left_margin(
            widget.fontMetrics(),
            max_val,
            value_formatter=widget._axis_value_formatter if widget._is_time_mode() else None,
        ),
    )

    if widget.hover_index != -1 and 0 <= widget.hover_index < n:
        lines = None
        if widget.hover_index != was_hover_index or not widget.tooltip_window.isVisible():
            val = values[widget.hover_index]
            label = widget._get_labels()[widget.hover_index]

            lines = []
            if label:
                lines.append(
                    {
                        "text": label,
                        "header": True,
                        "value": widget._format_metric_value(val, compact=False),
                    }
                )
            else:
                lines.append(
                    {
                        "text": ("Time" if widget._is_time_mode() else "Reviews"),
                        "header": True,
                        "value": widget._format_metric_value(val, with_unit=False, compact=False),
                    }
                )

            if getattr(widget, "cumulative_visible", False):
                cum_data = widget._get_cumulative()
                running_total = cum_data[widget.hover_index]
                lines.append(
                    {
                        "id": "total",
                        "text": f"Total: {widget._format_metric_value(running_total, compact=False)}",
                        "bold": True,
                    }
                )

        show_tooltip_near(
            widget,
            widget.tooltip_window,
            event.pos(),
            lines=lines,
            x_offset=15,
            y_offset=15,
            show_only_if_hidden=True,
        )
    else:
        widget.tooltip_window.hide()
def mouse_double_click_event_impl(widget, event):
    if widget.doubleClicked:
        widget.doubleClicked()
    QWidget.mouseDoubleClickEvent(widget, event)


def wheel_event_impl(widget, event):
    current_vals = [d[1] if isinstance(d, (list, tuple)) else d for d in widget.data]
    max_val = max(current_vals) if current_vals else 1
    fmt = widget._axis_value_formatter if widget._is_time_mode() else None
    margin_left = ChartGeometry.calculate_dynamic_left_margin(widget.fontMetrics(), max_val, value_formatter=fmt)
    values = [d[1] if isinstance(d, (list, tuple)) else d for d in widget._full_data]
    margin_right = ChartGeometry.calculate_dynamic_right_margin(
        widget.fontMetrics(),
        values,
        getattr(widget, "cumulative_visible", False),
        value_formatter=fmt,
    )
    plot_width = widget.width() - margin_left - margin_right

    if widget.handle_wheel_zoom(event, margin_left, plot_width):
        return
    QWidget.wheelEvent(widget, event)


def reset_zoom_impl(widget):
    reset_zoom_with_transition_impl(
        widget,
        old_attr="_transition_old_data",
        new_attr="_transition_new_data",
    )
