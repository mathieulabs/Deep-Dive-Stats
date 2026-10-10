# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import Qt

from ....chart_utils.tooltip import TooltipWindow


def init_chart_widget_state(
    widget,
    *,
    translucent=False,
    mouse_tracking=False,
    hover_attr=None,
    hover_value=-1,
    tooltip=False,
    hide_tooltip=True,
    animation_kwargs=None,
):
    if translucent:
        widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    if mouse_tracking:
        widget.setMouseTracking(True)
    if hover_attr:
        setattr(widget, str(hover_attr), hover_value)
    if tooltip:
        tooltip_window = TooltipWindow(widget)
        setattr(widget, "tooltip_window", tooltip_window)
        if hide_tooltip:
            tooltip_window.hide()
    widget.init_animation(**dict(animation_kwargs or {}))
