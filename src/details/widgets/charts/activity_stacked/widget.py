# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QWidget

from ...chart_utils import ChartAnimationMixin, ZoomableMixin
from ..common.metric import init_metric_chart_base
from .data_ops import (
    axis_value_formatter_for_mode_impl,
    axis_value_formatter_impl,
    binning_active_getter,
    compute_display_data_impl,
    finalize_data_transition_impl,
    format_metric_value_impl,
    get_avg_impl,
    get_cumulative_impl,
    get_display_data_impl,
    get_margins_impl,
    get_stats_text_impl,
    get_totals_impl,
    interpolate_relative_cumulative_impl,
    interpolate_relative_height_rows_impl,
    invalidate_all_data_caches_impl,
    invalidate_caches_impl,
    invalidate_geometry_caches_impl,
    is_time_mode_impl,
    refresh_data_colors_impl,
    set_average_mode_impl,
    set_chart_opacity_impl,
    set_cumulative_mode_impl,
    set_show_stats_impl,
    set_value_mode_impl,
    set_zoom_range_impl,
    update_data_impl,
)
from .event_ops import (
    change_event_impl,
    hide_event_impl,
    leave_event_impl,
    mouse_move_event_impl,
    mouse_press_event_impl,
    mouse_release_event_impl,
    reset_zoom_impl,
    resize_event_impl,
    wheel_event_impl,
)
from .render_ops import draw_bottom_stats_impl, paint_event_impl


class ActivityStackedChart(ZoomableMixin, ChartAnimationMixin, QWidget):
    """
    A widget that displays a stacked bar chart.
    Data format: List of dicts with series keys and optional `pretty_date`.
    """

    def __init__(self, data, series_config, parent=None, adaptive_binning=True):
        super().__init__(parent)
        self.series_config = series_config
        init_metric_chart_base(
            self,
            data,
            adaptive_binning=adaptive_binning,
            min_height=150,
            show_hover_marker=True,
        )

        self._totals_cache = None
        self._avg_cache = None
        self._cumulative_cache = None
        self._margin_cache = None
        self._binned_data_cache = None
        self._data_transition_active = False
        self._transition_old_display_data = []
        self._transition_new_display_data = []
        self._global_transition_mode = None
        self._transition_align_right = False
        self._relative_height_transition = False
        self._intensity_by_value_coloring = False
        self._bar_width_ratio = 1.0
        self._scaffold_cache_key = None
        self._scaffold_cache_pixmap = None
        self._chrome_cache_key = None
        self._chrome_cache_pixmap = None
        self.value_mode = "reviews"
        self.chart_opacity_pct = 100
        self.avg_visible = True
        self.avg_on_active_days = False
        self.show_stats = True
        self.cumulative_visible = False

    def set_chart_opacity(self, pct):
        return set_chart_opacity_impl(self, pct)

    def _get_margins(self):
        return get_margins_impl(self)

    @property
    def binning_active(self):
        return binning_active_getter(self)

    def set_show_stats(self, enabled):
        return set_show_stats_impl(self, enabled)

    def set_cumulative_mode(self, visible):
        return set_cumulative_mode_impl(self, visible)

    def refresh_data_colors(self):
        return refresh_data_colors_impl(self)

    def set_average_mode(self, visible, on_active_days):
        return set_average_mode_impl(self, visible, on_active_days)

    def set_value_mode(self, mode):
        return set_value_mode_impl(self, mode)

    def _is_time_mode(self):
        return is_time_mode_impl(self)

    def _format_metric_value(self, value, with_unit=True, per_day=False, axis=False, compact=True):
        return format_metric_value_impl(
            self,
            value,
            with_unit=with_unit,
            per_day=per_day,
            axis=axis,
            compact=compact,
        )

    def _axis_value_formatter(self, value):
        return axis_value_formatter_impl(self, value)

    def _axis_value_formatter_for_mode(self, mode, value):
        return axis_value_formatter_for_mode_impl(mode, value)

    def _invalidate_data_caches(self):
        return invalidate_all_data_caches_impl(self)

    def _compute_display_data(self, source_data):
        return compute_display_data_impl(self, source_data)

    def _get_display_data(self):
        return get_display_data_impl(self)

    def _get_totals(self):
        return get_totals_impl(self)

    def _get_avg(self):
        return get_avg_impl(self)

    def get_stats_text(self):
        return get_stats_text_impl(self)

    def _get_cumulative(self):
        return get_cumulative_impl(self)

    def mouseMoveEvent(self, event):
        return mouse_move_event_impl(self, event)

    def leaveEvent(self, event):
        return leave_event_impl(self, event)

    def hideEvent(self, event):
        return hide_event_impl(self, event)

    def changeEvent(self, event):
        return change_event_impl(self, event)

    def _invalidate_geometry_caches(self):
        return invalidate_geometry_caches_impl(self)

    def _invalidate_caches(self):
        return invalidate_caches_impl(self)

    def set_zoom_range(self, start_idx, end_idx):
        return set_zoom_range_impl(self, start_idx, end_idx)

    def update_data(
        self,
        new_data,
        adaptive_binning=None,
        transition_mode=None,
        transition_align_right=None,
    ):
        return update_data_impl(
            self,
            new_data,
            adaptive_binning=adaptive_binning,
            transition_mode=transition_mode,
            transition_align_right=transition_align_right,
        )

    def _finalize_data_transition(self):
        return finalize_data_transition_impl(self)

    def _interpolate_relative_height_rows(self, t):
        return interpolate_relative_height_rows_impl(self, t)

    def _interpolate_relative_cumulative(self, t):
        return interpolate_relative_cumulative_impl(self, t)

    def wheelEvent(self, event):
        return wheel_event_impl(self, event)

    def reset_zoom(self):
        return reset_zoom_impl(self)

    def mousePressEvent(self, event):
        return mouse_press_event_impl(self, event)

    def resizeEvent(self, event):
        return resize_event_impl(self, event)

    def mouseReleaseEvent(self, event):
        return mouse_release_event_impl(self, event)

    def paintEvent(self, event):
        return paint_event_impl(self, event)

    def draw_bottom_stats(self, painter, plot_w, h, margin_left, margin_bottom):
        return draw_bottom_stats_impl(self, painter, plot_w, h, margin_left, margin_bottom)
