# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QColor, QWidget

from ...chart_utils import ChartAnimationMixin, ZoomableMixin
from ..common.metric import axis_value_formatter_for_mode_impl, init_metric_chart_base
from .data_ops import (
    axis_value_formatter_impl,
    binning_active_getter,
    compute_display_data_impl,
    finalize_data_transition_impl,
    format_metric_value_impl,
    get_averages_impl,
    get_cumulative_impl,
    get_display_data_impl,
    get_labels_impl,
    get_margins_impl,
    get_max_val_impl,
    get_stats_text_impl,
    get_values_impl,
    interpolate_relative_cumulative_impl,
    interpolate_relative_height_values_impl,
    invalidate_caches_impl,
    invalidate_data_caches_impl,
    invalidate_geometry_caches_impl,
    is_time_mode_impl,
    refresh_data_colors_impl,
    set_average_mode_impl,
    set_chart_opacity_impl,
    set_cumulative_mode_impl,
    set_show_stats_impl,
    set_value_mode_impl,
    trace_activity_state_impl,
    update_data_impl,
)
from .event_ops import (
    change_event_impl,
    hide_event_impl,
    leave_event_impl,
    mouse_double_click_event_impl,
    mouse_move_event_impl,
    mouse_press_event_impl,
    mouse_release_event_impl,
    reset_zoom_impl,
    resize_event_impl,
    set_zoom_range_impl,
    wheel_event_impl,
)
from .render_ops import draw_bottom_stats_impl, paint_event_impl


class ActivityChart(ZoomableMixin, ChartAnimationMixin, QWidget):
    def __init__(self, data, color="#8ab4f8", chart_type="line", parent=None, adaptive_binning=True):
        super().__init__(parent)
        self.color = QColor(color)
        self.chart_type = chart_type
        self.doubleClicked = None
        init_metric_chart_base(
            self,
            data,
            adaptive_binning=adaptive_binning,
            min_height=200,
            expanding_size_policy=True,
            show_hover_marker=True,
        )

        self._avg_val_cache = None
        self._cumulative_cache = None
        self._values_cache = None
        self._labels_cache = None
        self._max_val_cache = None
        self._has_labels_cache = None
        self._path_cache = None
        self._area_path_cache = None
        self._cum_path_cache = None
        self._binned_data_cache = None
        self._data_transition_active = False
        self._transition_old_data = []
        self._transition_new_data = []
        self._global_transition_mode = None
        self._transition_align_right = False
        self._relative_height_transition = False
        self._scaffold_cache_key = None
        self._scaffold_cache_pixmap = None
        self._chrome_cache_key = None
        self._chrome_cache_pixmap = None

        self.avg_visible = True
        self.avg_on_active_days = False
        self.value_mode = "reviews"
        self.chart_opacity_pct = 100

    def set_chart_opacity(self, pct):
        return set_chart_opacity_impl(self, pct)

    @property
    def binning_active(self):
        return binning_active_getter(self)

    def refresh_data_colors(self):
        return refresh_data_colors_impl(self)

    def set_average_mode(self, visible, on_active_days):
        return set_average_mode_impl(self, visible, on_active_days)

    def set_value_mode(self, mode):
        return set_value_mode_impl(self, mode)

    def _axis_value_formatter_for_mode(self, mode, value):
        return axis_value_formatter_for_mode_impl(mode, value)

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

    def set_cumulative_mode(self, visible):
        return set_cumulative_mode_impl(self, visible)

    def _get_averages(self):
        return get_averages_impl(self)

    def get_stats_text(self):
        return get_stats_text_impl(self)

    def _get_cumulative(self):
        return get_cumulative_impl(self)

    def set_show_stats(self, enabled):
        return set_show_stats_impl(self, enabled)

    def _get_margins(self):
        return get_margins_impl(self)

    def _compute_display_data(self, source_data):
        return compute_display_data_impl(self, source_data)

    def _get_display_data(self):
        return get_display_data_impl(self)

    def _get_values(self):
        return get_values_impl(self)

    def _get_labels(self):
        return get_labels_impl(self)

    def _get_max_val(self):
        return get_max_val_impl(self)

    def _invalidate_geometry_caches(self):
        return invalidate_geometry_caches_impl(self)

    def _invalidate_data_caches(self):
        return invalidate_data_caches_impl(self)

    def _invalidate_caches(self):
        return invalidate_caches_impl(self)

    def _trace_activity_state(self, event_name, **fields):
        return trace_activity_state_impl(self, event_name, **fields)

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

    def _interpolate_relative_height_values(self, t):
        return interpolate_relative_height_values_impl(self, t)

    def _interpolate_relative_cumulative(self, t):
        return interpolate_relative_cumulative_impl(self, t)

    def _finalize_data_transition(self):
        return finalize_data_transition_impl(self)

    def mouseMoveEvent(self, event):
        return mouse_move_event_impl(self, event)

    def leaveEvent(self, event):
        return leave_event_impl(self, event)

    def hideEvent(self, event):
        return hide_event_impl(self, event)

    def changeEvent(self, event):
        return change_event_impl(self, event)

    def mouseDoubleClickEvent(self, event):
        return mouse_double_click_event_impl(self, event)

    def set_zoom_range(self, start_idx, end_idx):
        return set_zoom_range_impl(self, start_idx, end_idx)

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

