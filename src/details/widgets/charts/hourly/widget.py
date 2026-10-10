# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QColor, QWidget

from ....animations.chart_mixin import ChartAnimationMixin
from ..common import init_chart_widget_state
from .data_ops import (
    current_values_snapshot_impl,
    get_margin_right_impl,
    get_stats_text_impl,
    get_tooltip_text_impl,
    interpolate_series_fast_impl,
    refresh_data_colors_impl,
    set_chart_opacity_impl,
    set_cumulative_mode_impl,
    snapshot_from_data_impl,
    update_data_impl,
)
from .event_ops import (
    change_event_impl,
    clear_hover_impl,
    hide_event_impl,
    leave_event_impl,
    mouse_move_event_impl,
)
from .render_ops import (
    draw_bars_impl,
    draw_bottom_stats_impl,
    draw_success_rate_area_impl,
    draw_x_axis_impl,
    paint_event_impl,
)


class HourlyBreakdownChart(ChartAnimationMixin, QWidget):
    def __init__(self, data_dict, parent=None):
        super().__init__(parent)
        self.data_dict = data_dict
        self.setMinimumHeight(200)
        self.show_cumulative_axis = True

        self.max_val = max([v["total"] for v in self.data_dict.values()]) if self.data_dict else 1
        if self.max_val == 0:
            self.max_val = 1

        from ....ui import Config, get_chart_color

        self.bar_color = QColor(get_chart_color(Config.COLOR_BAR, self))
        self.chart_opacity_pct = 100

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
        self._transition_old_totals = [0.0] * 24
        self._transition_new_totals = [0.0] * 24
        self._transition_old_correct = [0.0] * 24
        self._transition_new_correct = [0.0] * 24
        self._transition_old_max = 1.0
        self._transition_new_max = 1.0
        self._data_transition_render_cache = {}
        self._scaffold_cache_key = None
        self._scaffold_cache_pixmap = None
        self._overlay_cache_key = None
        self._overlay_cache_pixmap = None

    def set_cumulative_mode(self, visible):
        return set_cumulative_mode_impl(self, visible)

    def _get_margin_right(self):
        return get_margin_right_impl(self)

    def _snapshot_from_data(self, data_dict):
        return snapshot_from_data_impl(self, data_dict)

    def _interpolate_series_fast(self, old_values, new_values, t):
        return interpolate_series_fast_impl(self, old_values, new_values, t)

    def _current_values_snapshot(self):
        return current_values_snapshot_impl(self)

    def set_chart_opacity(self, pct):
        return set_chart_opacity_impl(self, pct)

    def refresh_data_colors(self):
        return refresh_data_colors_impl(self)

    def update_data(self, new_data):
        return update_data_impl(self, new_data)

    def get_tooltip_text(self, h_idx):
        return get_tooltip_text_impl(self, h_idx)

    def get_stats_text(self):
        return get_stats_text_impl(self)

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

    def draw_bottom_stats(self, painter, plot_w, h, margin_left, margin_bottom):
        return draw_bottom_stats_impl(self, painter, plot_w, h, margin_left, margin_bottom)

    def draw_success_rate_area(self, painter, plot_w, plot_h, margin_left, margin_top, rates, active_mask, visibility, disappearing_mask):
        return draw_success_rate_area_impl(self, painter, plot_w, plot_h, margin_left, margin_top, rates, active_mask, visibility, disappearing_mask)

    def draw_bars(self, painter, plot_w, plot_h, margin_left, margin_top, totals, draw_ratios):
        return draw_bars_impl(self, painter, plot_w, plot_h, margin_left, margin_top, totals, draw_ratios)

    def draw_x_axis(self, painter, plot_w, total_h, margin_left, margin_bottom):
        return draw_x_axis_impl(self, painter, plot_w, total_h, margin_left, margin_bottom)
