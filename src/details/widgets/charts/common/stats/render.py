# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ....chart_utils.drawing import draw_wrapped_bottom_stats


def draw_chart_bottom_stats(
    widget,
    painter,
    plot_w,
    h,
    margin_left,
    margin_bottom,
    *,
    stats=None,
    require_positive_total=False,
):
    if not getattr(widget, "show_stats", False):
        return
    if require_positive_total and getattr(widget, "total_cards", 0) <= 0:
        return
    if stats is None:
        stats = widget.get_stats_text()
    draw_wrapped_bottom_stats(
        painter,
        stats,
        plot_w=plot_w,
        height=h,
        margin_left=margin_left,
        margin_bottom=margin_bottom,
        widget=widget,
    )
