# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QSizePolicy

from ....chart_utils import FloatingAvgLabel, TooltipWindow


def init_metric_chart_base(
    widget,
    data,
    *,
    adaptive_binning=True,
    min_height=None,
    expanding_size_policy=False,
    show_hover_marker=True,
):
    widget._full_data = data
    widget.data = data
    widget.adaptive_binning = adaptive_binning
    widget.binning_override = None

    widget.setMouseTracking(True)
    widget.hover_index = -1
    widget.hover_avg = False
    widget.show_hover_marker = bool(show_hover_marker)

    if expanding_size_policy:
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    if min_height is not None:
        widget.setMinimumHeight(int(min_height))

    widget.tooltip_window = TooltipWindow(widget)
    widget.avg_tooltip = FloatingAvgLabel(widget)
    widget.init_animation()
    widget.init_zoom(len(data or []))
