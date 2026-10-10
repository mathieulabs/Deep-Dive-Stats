# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..common.discrete import (
    change_event_impl,
    clear_hover_impl,
    hide_event_impl,
    leave_event_impl,
    mouse_move_discrete_chart,
)
from ...chart_utils.geometry import ChartGeometry


def mouse_move_event_impl(widget, event):
    margin_left = ChartGeometry.calculate_dynamic_left_margin(widget.fontMetrics(), widget.max_val)
    margin_right = widget._get_margin_right()
    margin_bottom = ChartGeometry.MARGIN_BOTTOM
    margin_top = ChartGeometry.MARGIN_TOP + 10
    return mouse_move_discrete_chart(
        widget,
        event,
        has_data=bool(widget.data_dict),
        points_count=24,
        margins=(margin_left, margin_right, margin_bottom, margin_top),
        tooltip_text_getter=lambda idx, _count: widget.get_tooltip_text(idx),
    )
