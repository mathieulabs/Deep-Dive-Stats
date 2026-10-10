# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QWidget

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
    update_avg_hover_state,
)


def mouse_move_event_impl(widget, event):
    display_data = widget._get_display_data()
    if not display_data:
        return
    plot = get_plot_geometry(widget)
    margin_left = plot["margin_left"]
    margin_top = plot["margin_top"]
    avail_w = plot["plot_width"]
    avail_h = plot["plot_height"]

    if avail_w <= 0:
        return

    if widget.handle_selection_move(event, margin_left, avail_w):
        return

    pos = event.pos()
    x = pos.x() - margin_left
    n = len(display_data)
    if n <= 0:
        return

    idx = resolve_hover_index(x, avail_w, n)

    was_hover_index = widget.hover_index
    if widget.hover_index != idx:
        widget.hover_index = idx
        widget.update()

    totals = widget._get_totals()
    max_val = max(totals) if totals else 1
    if max_val == 0:
        max_val = 1

    mouse_y = pos.y()
    in_plot_x = (0 <= x < avail_w)
    in_plot_y = (margin_top <= mouse_y <= (margin_top + avail_h))
    avg_val = 0
    if getattr(widget, "avg_visible", True) and totals:
        avg_val = widget._get_avg()
    was_hovering, y_avg = update_avg_hover_state(
        widget,
        avg_value=avg_val,
        max_val=max_val,
        margin_top=margin_top,
        plot_height=avail_h,
        mouse_y=mouse_y,
        in_plot_x=in_plot_x,
        in_plot_y=in_plot_y,
    )

    if widget.hover_avg != was_hovering:
        widget.update()

    refresh_avg_hover_tooltip(
        widget,
        avg_value=avg_val,
        y_avg=y_avg,
        anchor_x_local=margin_left,
    )

    lines = None
    if widget.hover_index != was_hover_index or not widget.tooltip_window.isVisible():
        item = display_data[widget.hover_index]
        total_at_index = sum(item.get(c["key"], 0) for c in widget.series_config)
        header_val = widget._format_metric_value(total_at_index, compact=False) if total_at_index > 0 else ""
        lines = [{"text": item["pretty_date"], "header": True, "value": header_val}]
        for config in widget.series_config:
            val = item.get(config["key"], 0)
            if val > 0:
                lines.append(
                    {
                        "id": config["key"],
                        "text": config["label"],
                        "value": widget._format_metric_value(
                            val,
                            with_unit=widget._is_time_mode(),
                            compact=False,
                        ),
                        "color": config["color"],
                    }
                )
        cum_data = widget._get_cumulative()
        running_total = cum_data[widget.hover_index]
        lines.append({"id": "total", "text": f"Total: {widget._format_metric_value(running_total, compact=False)}", "bold": True})

    show_tooltip_near(
        widget,
        widget.tooltip_window,
        event.pos(),
        lines=lines,
        x_offset=15,
        y_offset=15,
        show_only_if_hidden=True,
    )


def wheel_event_impl(widget, event):
    margin_left, margin_right = widget._get_margins()
    plot_width = widget.width() - margin_left - margin_right
    if widget.handle_wheel_zoom(event, margin_left, plot_width):
        return
    QWidget.wheelEvent(widget, event)


def reset_zoom_impl(widget):
    reset_zoom_with_transition_impl(
        widget,
        old_attr="_transition_old_display_data",
        new_attr="_transition_new_display_data",
    )
