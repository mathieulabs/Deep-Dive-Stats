# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Base class for all FSRS chart widgets (Stability, Difficulty, Retrievability)."""

from aqt.qt import QWidget

from ....animations.chart_mixin import ChartAnimationMixin
from ..common import init_chart_widget_state
from .data_ops import (
    binning_active_getter,
    current_values_snapshot_impl,
    get_margins_impl,
    get_stats_text_impl,
    normalize_data_dict_impl,
    set_chart_opacity_impl,
    update_data_impl,
)
from .event_ops import (
    change_event_impl,
    clear_hover_impl,
    hide_event_impl,
    leave_event_impl,
    mouse_move_event_impl,
)
from .render_ops import paint_event_impl


class FSRSBaseChart(ChartAnimationMixin, QWidget):
    def __init__(self, data_dict, title="", parent=None, adaptive_binning=True):
        super().__init__(parent)
        self.adaptive_binning = adaptive_binning
        self.binning_override = None
        self.data_dict = data_dict
        self.title = title
        self.data_dict = self._normalize_data_dict(self.data_dict)
        self.setMinimumHeight(120)
        self.data_list = sorted(self.data_dict.items())

        self.max_val = max([v for _, v in self.data_list]) if self.data_list else 1
        self.total_cards = sum([v for _, v in self.data_list])
        self.show_stats = True
        self.show_cumulative_axis = True

        init_chart_widget_state(
            self,
            translucent=True,
            mouse_tracking=True,
            hover_attr="hover_index",
            hover_value=-1,
            tooltip=True,
            hide_tooltip=True,
        )
        self._data_transition_active = False
        self._transition_old_values = []
        self._transition_new_values = []
        self._transition_old_max = 1.0
        self._transition_new_max = 1.0
        self._anim_draw_values = []
        self._anim_draw_ratios = []
        self.chart_opacity_pct = 100
        self._non_cumulative_margin_right = 8
        self._scaffold_cache_key = None
        self._scaffold_cache_pixmap = None

    def _normalize_data_dict(self, data_dict):
        return normalize_data_dict_impl(self, data_dict)

    @property
    def binning_active(self):
        return binning_active_getter(self)

    def _get_margins(self):
        return get_margins_impl(self)

    def update_data(self, new_data_dict, adaptive_binning=None):
        return update_data_impl(self, new_data_dict, adaptive_binning=adaptive_binning)

    def _current_values_snapshot(self):
        return current_values_snapshot_impl(self)

    def get_tooltip_text(self, k, v):
        return f"{k}: {v} cards"

    def mouseMoveEvent(self, event):
        return mouse_move_event_impl(self, event)

    def leaveEvent(self, event):
        return leave_event_impl(self, event)

    def hideEvent(self, event):
        return hide_event_impl(self, event)

    def changeEvent(self, event):
        return change_event_impl(self, event)

    def _clear_hover(self):
        return clear_hover_impl(self)

    def paintEvent(self, event):
        return paint_event_impl(self, event)

    def set_chart_opacity(self, pct):
        return set_chart_opacity_impl(self, pct)

    def draw_bars(self, painter, plot_w, plot_h, margin_left, margin_top):
        pass

    def draw_extras(self, painter, plot_w, plot_h, margin_left, margin_top, margin_bottom, w, h):
        pass

    def get_stats_text(self):
        return get_stats_text_impl(self)
