# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..common.discrete import (
    change_event_impl,
    clear_hover_impl,
    hide_event_impl,
    leave_event_impl,
    mouse_move_discrete_chart,
)


def mouse_move_event_impl(widget, event):
    dist = widget.data_dict.get("distribution", {})
    points_count = widget._get_points_count()
    return mouse_move_discrete_chart(
        widget,
        event,
        has_data=bool(dist),
        points_count=points_count,
        margins=widget._get_margins(),
        tooltip_text_getter=lambda idx, count: widget.get_tooltip_text(idx, count),
    )
