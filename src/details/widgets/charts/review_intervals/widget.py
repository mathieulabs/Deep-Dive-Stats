# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QColor, QWidget

from ....animations.chart_mixin import ChartAnimationMixin
from ...chart_utils.geometry import ChartGeometry
from ..common.discrete import init_discrete_chart_common_state
from .data_ops import (
    binning_active_getter,
    build_display_values_impl,
    compute_stats_impl,
    current_values_snapshot_impl,
    day_range_impl,
    get_points_count_impl,
    get_stats_text_impl,
    get_tooltip_text_impl,
    interpolate_relative_cumulative_line_impl,
    invalidate_data_caches_impl,
    refresh_data_colors_impl,
    set_chart_opacity_impl,
    set_cumulative_mode_impl,
    set_view_filter_impl,
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
    draw_cumulative_area_impl,
    draw_stats_text_impl,
    draw_x_axis_impl,
    paint_event_impl,
)


class ReviewIntervalsChart(ChartAnimationMixin, QWidget):
    def __init__(self, data_dict, parent=None, adaptive_binning=True, filter_mode="95_percent"):
        super().__init__(parent)
        self.data_dict = data_dict
        init_discrete_chart_common_state(self, adaptive_binning=adaptive_binning, opacity_pct=100)
        self.filter_mode = str(filter_mode or "95_percent")
        self.max_days = 31
        self.max_val = 1
        self.filtered_dist = {}
        self._view_initialized = False

        self._compute_stats()

        from ....ui import Config, get_chart_color
        self.bar_color = QColor(get_chart_color(Config.COLOR_BAR, self))
        self.set_view_filter(self.filter_mode)

    @property
    def binning_active(self):
        return binning_active_getter(self)

    def set_cumulative_mode(self, visible):
        return set_cumulative_mode_impl(self, visible)

    def _invalidate_data_caches(self):
        return invalidate_data_caches_impl(self)

    def _get_points_count(self):
        return get_points_count_impl(self)

    def _day_range(self, i, points_count):
        return day_range_impl(self, i, points_count)

    def _get_margins(self):
        ml = ChartGeometry.calculate_dynamic_left_margin(self.fontMetrics(), self.max_val)
        mr = ChartGeometry.calculate_dynamic_right_margin(self.fontMetrics(), [self.data_dict.get("total", 0)], True)
        mb = ChartGeometry.MARGIN_BOTTOM + (50 if self.show_stats else 0)
        mt = ChartGeometry.MARGIN_TOP
        return ml, mr, mb, mt

    def _build_display_values(self, dist, max_days):
        return build_display_values_impl(self, dist, max_days)

    def _current_values_snapshot(self):
        return current_values_snapshot_impl(self)

    def _interpolate_relative_cumulative_line(self, t):
        return interpolate_relative_cumulative_line_impl(self, t)

    def set_chart_opacity(self, pct):
        return set_chart_opacity_impl(self, pct)

    def set_view_filter(self, filter_mode, transition_mode=None):
        return set_view_filter_impl(self, filter_mode, transition_mode=transition_mode)

    def refresh_data_colors(self):
        return refresh_data_colors_impl(self)

    def update_data(self, new_data, adaptive_binning=None, transition_mode=None):
        return update_data_impl(self, new_data, adaptive_binning=adaptive_binning, transition_mode=transition_mode)

    def get_tooltip_text(self, idx, points_count):
        return get_tooltip_text_impl(self, idx, points_count)

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

    def _compute_stats(self):
        return compute_stats_impl(self)

    def paintEvent(self, event):
        return paint_event_impl(self, event)

    def draw_cumulative_area(self, painter, plot_w, plot_h, margin_left, margin_top, total_cards):
        return draw_cumulative_area_impl(self, painter, plot_w, plot_h, margin_left, margin_top, total_cards)

    def draw_bars(self, painter, plot_w, plot_h, margin_left, margin_top):
        return draw_bars_impl(self, painter, plot_w, plot_h, margin_left, margin_top)

    def draw_x_axis(self, painter, plot_w, total_h, margin_left, margin_bottom):
        return draw_x_axis_impl(self, painter, plot_w, total_h, margin_left, margin_bottom)

    def draw_stats_text(self, painter, plot_w, h, margin_left, margin_bottom):
        return draw_stats_text_impl(self, painter, plot_w, h, margin_left, margin_bottom)

    def get_stats_text(self):
        return get_stats_text_impl(self)
