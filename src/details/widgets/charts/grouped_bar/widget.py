# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QWidget

from ...chart_utils import ChartAnimationMixin
from ..common import get_review_button_colors, init_chart_widget_state
from .data_ops import (
    current_values_snapshot_impl,
    flatten_grouped_values_impl,
    has_meaningful_data_for_animation_impl,
    interpolate_series_fast_impl,
    refresh_data_colors_impl,
    set_chart_opacity_impl,
    update_data_impl,
)
from .event_ops import change_event_impl, hide_event_impl, leave_event_impl, mouse_move_event_impl, resize_event_impl
from .layout_ops import get_bar_at_pos_impl, recalculate_layout_impl
from .render_ops import paint_event_impl


class GroupedBarWidget(ChartAnimationMixin, QWidget):
    """Grouped bar chart. Data format: {'learning': [..], 'young': [..], 'mature': [..]}."""

    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data
        self.hover_info = None
        self.setMinimumHeight(150)

        self.max_val = 1
        self.bar_rects = []
        self.group_labels_rects = []

        self.colors = get_review_button_colors(self)
        self.group_labels = {"learning": "Learning", "young": "Young", "mature": "Mature"}
        self.button_labels = ["Again", "Hard", "Good", "Easy"]
        self._group_order = ["learning", "young", "mature"]
        self._buttons_per_group = len(self.button_labels)
        self._data_transition_active = False
        self._transition_old_values = []
        self._transition_new_values = []
        self._transition_old_max = 1.0
        self._transition_new_max = 1.0
        self._has_real_data = False
        self._scaffold_cache_key = None
        self._scaffold_cache_pixmap = None
        self._chrome_cache_key = None
        self._chrome_cache_pixmap = None

        all_values = []
        for values in self.data.values():
            all_values.extend(values)
        self.max_val = max(all_values) if all_values and max(all_values) > 0 else 1
        self._has_real_data = any(float(v or 0.0) > 0.0 for v in all_values)

        self.chart_opacity_pct = 100
        init_chart_widget_state(
            self,
            mouse_tracking=True,
            tooltip=True,
            hide_tooltip=False,
        )

    def refresh_data_colors(self):
        return refresh_data_colors_impl(self)

    def set_chart_opacity(self, pct):
        return set_chart_opacity_impl(self, pct)

    def _has_meaningful_data_for_animation(self):
        return has_meaningful_data_for_animation_impl(self)

    def _flatten_grouped_values(self, data):
        return flatten_grouped_values_impl(self, data)

    def _interpolate_series_fast(self, old_values, new_values, t):
        return interpolate_series_fast_impl(self, old_values, new_values, t)

    def _current_values_snapshot(self):
        return current_values_snapshot_impl(self)

    def update_data(self, new_data, transition_mode=None):
        return update_data_impl(self, new_data, transition_mode=transition_mode)

    def resizeEvent(self, event):
        return resize_event_impl(self, event)

    def _recalculate_layout(self):
        return recalculate_layout_impl(self)

    def _get_bar_at_pos(self, pos):
        return get_bar_at_pos_impl(self, pos)

    def mouseMoveEvent(self, event):
        return mouse_move_event_impl(self, event)

    def leaveEvent(self, event):
        return leave_event_impl(self, event)

    def hideEvent(self, event):
        return hide_event_impl(self, event)

    def changeEvent(self, event):
        return change_event_impl(self, event)

    def paintEvent(self, event):
        return paint_event_impl(self, event)
