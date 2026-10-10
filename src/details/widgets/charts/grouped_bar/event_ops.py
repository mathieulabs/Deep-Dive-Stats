# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QWidget

from ...chart_utils.tooltip import hide_tooltip_targets, hide_tooltips_on_window_deactivate, show_tooltip_near
from ...chart_utils.formatting import fmt_num


def resize_event_impl(widget, event):
    QWidget.resizeEvent(widget, event)
    widget._recalculate_layout()


def mouse_move_event_impl(widget, event):
    pos = event.pos()
    bar = widget._get_bar_at_pos(pos)

    previous = widget.hover_info
    if bar:
        group_name = widget.group_labels.get(bar["group"], bar["group"])
        btn_name = widget.button_labels[bar["btn_idx"]]
        value = bar["val"]
        lines = [
            {"text": f"{group_name} - {btn_name}", "header": True},
            {"text": "Value", "value": fmt_num(value)},
        ]
        show_tooltip_near(
            widget,
            widget.tooltip_window,
            pos,
            lines=lines,
            x_offset=15,
            y_offset=15,
            show_only_if_hidden=True,
        )
        widget.hover_info = (group_name, btn_name, value, bar["rect"])
    else:
        hide_tooltip_targets(widget, "tooltip_window")
        widget.hover_info = None

    if widget.hover_info != previous:
        widget.update()


def leave_event_impl(widget, event):
    widget.hover_info = None
    hide_tooltip_targets(widget, "tooltip_window")
    widget.update()


def hide_event_impl(widget, event):
    hide_tooltip_targets(widget, "tooltip_window")
    QWidget.hideEvent(widget, event)


def change_event_impl(widget, event):
    hide_tooltips_on_window_deactivate(widget, event, "tooltip_window")
    QWidget.changeEvent(widget, event)
