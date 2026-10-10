# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QWidget

from ....chart_utils.tooltip import (
    hide_tooltip_targets,
    hide_tooltips_on_window_deactivate,
    show_tooltip_text_near,
)


def resolve_discrete_hover_index(pos, *, width, height, margins, points_count):
    margin_left, margin_right, margin_bottom, margin_top = margins
    if points_count <= 0:
        return -1
    if not (margin_left <= pos.x() <= width - margin_right and margin_top <= pos.y() <= height - margin_bottom):
        return -1

    plot_w = width - margin_left - margin_right
    if plot_w <= 0:
        return -1

    step_x = plot_w / points_count
    idx = int((pos.x() - margin_left) / step_x)
    return max(0, min(points_count - 1, idx))


def mouse_move_discrete_chart(widget, event, *, has_data, points_count, margins, tooltip_text_getter):
    if not has_data:
        return

    pos = event.pos()
    found_idx = resolve_discrete_hover_index(
        pos,
        width=widget.width(),
        height=widget.height(),
        margins=margins,
        points_count=points_count,
    )
    if found_idx == -1:
        widget._clear_hover()
        return

    if widget.hover_index != found_idx:
        widget.hover_index = found_idx
        widget.update()

    text = tooltip_text_getter(found_idx, points_count)
    show_tooltip_text_near(
        widget,
        widget.tooltip_window,
        pos,
        text,
        x_offset=15,
        y_offset=15,
        show_only_if_hidden=True,
    )


def leave_event_impl(widget, event):
    widget._clear_hover()


def hide_event_impl(widget, event):
    widget._clear_hover()
    QWidget.hideEvent(widget, event)


def change_event_impl(widget, event):
    hide_tooltips_on_window_deactivate(widget, event, "tooltip_window")
    QWidget.changeEvent(widget, event)


def clear_hover_impl(widget):
    if widget.hover_index != -1:
        widget.hover_index = -1
        widget.update()
    hide_tooltip_targets(widget, "tooltip_window")
