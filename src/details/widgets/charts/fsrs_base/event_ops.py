# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ...chart_utils.formatting import fmt_num
from ..common.discrete import (
    change_event_impl,
    clear_hover_impl,
    hide_event_impl,
    leave_event_impl,
    mouse_move_discrete_chart,
)
from .....i18n import tr_n


def mouse_move_event_impl(widget, event):
    return mouse_move_discrete_chart(
        widget,
        event,
        has_data=bool(widget.data_list),
        points_count=len(widget.data_list or []),
        margins=widget._get_margins(),
        tooltip_text_getter=lambda idx, _points_count: _tooltip_text(widget, idx),
    )


def _tooltip_text(widget, idx):
    text = widget.get_tooltip_text(*widget.data_list[idx])
    if getattr(widget, "cumulative_visible", False):  # Stability: the running total of its curve
        running = sum(v for _k, v in widget.data_list[: idx + 1])
        text += "\n" + tr_n("Total: {count} card", "Total: {count} cards", running, count=fmt_num(running))
    return text
