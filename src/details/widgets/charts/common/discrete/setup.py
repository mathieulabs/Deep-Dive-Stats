# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import Qt

from ....chart_utils.tooltip import TooltipWindow
from .data import reset_discrete_transition_state


def init_discrete_chart_common_state(widget, *, adaptive_binning, opacity_pct=100):
    widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    widget.show_stats = True
    widget.cumulative_visible = True
    widget.show_cumulative_axis = True
    widget.adaptive_binning = adaptive_binning
    widget.binning_override = None
    widget.binning_toggled_callback = None
    widget.chart_opacity_pct = int(opacity_pct)
    widget.hover_index = -1
    widget._display_values = []
    widget._points_count = 0
    widget._scaffold_cache_key = None
    widget._scaffold_cache_pixmap = None
    widget._chrome_cache_key = None
    widget._chrome_cache_pixmap = None
    reset_discrete_transition_state(widget)
    widget.setMouseTracking(True)
    widget.tooltip_window = TooltipWindow(widget)
    widget.tooltip_window.hide()
    widget.init_animation()
