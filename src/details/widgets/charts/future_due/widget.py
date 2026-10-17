# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QColor, QWidget

from ...chart_utils import ChartAnimationMixin
from ...chart_utils.geometry import ChartGeometry
from ..common.discrete import init_discrete_chart_common_state
from .data_ops import (
    binning_active_getter,
    build_display_values_impl,
    get_bin_day_range_for_impl,
    get_bin_day_range_impl,
    get_min_day_for_dist_impl,
    get_min_day_impl,
    get_points_count_for_dist_impl,
    get_points_count_impl,
    get_stats_text_impl,
    get_tooltip_text_impl,
    invalidate_data_caches_impl,
    refresh_data_colors_impl,
    set_chart_opacity_impl,
    set_cumulative_mode_impl,
    update_data_impl,
    update_max_val_impl,
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


class FutureDueChart(ChartAnimationMixin, QWidget):
    def __init__(self, data_dict, parent=None, adaptive_binning=True, show_backlog=False):
        super().__init__(parent)
        self.data_dict = data_dict
        self.show_backlog = show_backlog
        init_discrete_chart_common_state(self, adaptive_binning=adaptive_binning, opacity_pct=100)

        self.max_days = self.data_dict.get("max_days", 31)
        self._update_max_val()

        from ....ui import Config, get_chart_color
        self.bar_color = QColor(get_chart_color(Config.COLOR_FUTURE_DUE, self))
        self._points_count, self._display_values = self._build_display_values(
            self.data_dict.get("distribution", {}),
            self.max_days,
            self.show_backlog,
        )

    @property
    def binning_active(self):
        return binning_active_getter(self)

    def set_cumulative_mode(self, visible):
        return set_cumulative_mode_impl(self, visible)

    def _get_margins(self):
        fm = self.fontMetrics()
        ml = ChartGeometry.calculate_dynamic_left_margin(fm, self.max_val)
        mr = ChartGeometry.calculate_dynamic_right_margin(fm, [self.data_dict.get("total", 0)], True)
        mb = ChartGeometry.MARGIN_BOTTOM
        mt = ChartGeometry.MARGIN_TOP
        return ml, mr, mb, mt

    def _get_min_day(self):
        return get_min_day_impl(self)

    def _get_min_day_for_dist(self, dist, show_backlog):
        return get_min_day_for_dist_impl(self, dist, show_backlog)

    def _update_max_val(self):
        return update_max_val_impl(self)

    def _get_bin_day_range(self, idx, points_count):
        return get_bin_day_range_impl(self, idx, points_count)

    def _get_bin_day_range_for(self, idx, points_count, min_day, max_days):
        return get_bin_day_range_for_impl(self, idx, points_count, min_day, max_days)

    def _invalidate_data_caches(self):
        return invalidate_data_caches_impl(self)

    def _get_points_count(self):
        return get_points_count_impl(self)

    def _get_points_count_for_dist(self, dist, max_days, show_backlog):
        return get_points_count_for_dist_impl(self, dist, max_days, show_backlog)

    def _build_display_values(self, dist, max_days, show_backlog):
        return build_display_values_impl(self, dist, max_days, show_backlog)

    def set_chart_opacity(self, pct):
        return set_chart_opacity_impl(self, pct)

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

    def paintEvent(self, event):
        return paint_event_impl(self, event)

    def draw_cumulative_area(self, painter, plot_w, plot_h, margin_left, margin_top, total_cards):
        return draw_cumulative_area_impl(self, painter, plot_w, plot_h, margin_left, margin_top, total_cards)

    def draw_bars(self, painter, plot_w, plot_h, margin_left, margin_top):
        return draw_bars_impl(self, painter, plot_w, plot_h, margin_left, margin_top)

    def draw_x_axis(self, painter, plot_w, total_h, margin_left, margin_top, margin_bottom):
        return draw_x_axis_impl(self, painter, plot_w, total_h, margin_left, margin_top, margin_bottom)

    def draw_stats_text(self, painter, plot_w, h, margin_left, margin_bottom):
        return draw_stats_text_impl(self, painter, plot_w, h, margin_left, margin_bottom)

    def get_stats_text(self):
        return get_stats_text_impl(self)
