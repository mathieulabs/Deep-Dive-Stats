# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Multi-series retention chart with toggleable retention types."""

from aqt.qt import QEasingCurve, QSizePolicy, QWidget, pyqtSignal

from ...chart_utils import ChartAnimationMixin, FloatingAvgLabel, ZoomableMixin
from ..common import init_chart_widget_state
from .data_ops import (
    apply_zoom_to_data_impl,
    avg_from_display_series_impl,
    avg_from_series_rows_impl,
    binning_active_getter,
    calc_averages_impl,
    clear_data_transition_state_impl,
    compute_display_data_impl,
    extract_series_values_impl,
    get_data_range_impl,
    get_display_data_impl,
    get_display_n_impl,
    get_margin_right_impl,
    get_series_avg_alpha_impl,
    get_series_avg_y_impl,
    get_stats_text_impl,
    invalidate_data_caches_impl,
    on_animation_finished_impl,
    prepare_data_transition_impl,
    sample_series_values_impl,
    set_average_mode_impl,
    set_chart_opacity_impl,
    set_cumulative_mode_impl,
    series_totals_impl,
    set_fit_to_data_impl,
    set_min_reviews_impl,
    set_series_visible_impl,
    set_show_stats_impl,
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
    set_zoom_range_impl,
    wheel_event_impl,
)
from .render_ops import draw_bottom_stats_impl, draw_series_transition_impl, paint_event_impl
from ....logic.logger import log_swallowed


class RetentionChart(ZoomableMixin, ChartAnimationMixin, QWidget):
    """A multi-series line chart for displaying retention data with toggleable series."""

    SERIES_CONFIG = {
        "all": {"label": "All", "color": "#22c55e", "default_on": False},
        "young": {"label": "Young", "color": "#00BCD4", "default_on": True},
        "mature": {"label": "Mature", "color": "#4caf50", "default_on": True},
        "true": {"label": "True", "color": "#9fa8da", "default_on": False},
    }

    @staticmethod
    def _get_series_color(key, widget_or_context=None):
        try:
            from aqt import mw
            from ....ui import RETENTION_SERIES_COLOR_KEY, ConfigManager, get_color

            cfg = ConfigManager(mw).config
            color_key = RETENTION_SERIES_COLOR_KEY.get(key)
            if color_key:
                return get_color(cfg, color_key, widget_or_context)
        except Exception:
            log_swallowed()
        return RetentionChart.SERIES_CONFIG[key]["color"]

    totals_changed = pyqtSignal()

    def __init__(self, retention_data, parent=None, visible_series=None, adaptive_binning=True):
        super().__init__(parent)
        self.min_reviews = 0
        self.review_bars = True
        self.review_axis = False
        self.rounded = True
        self._bars_fade = None
        self._full_retention_data = retention_data or {}
        self.retention_data = retention_data or {}
        self.adaptive_binning = adaptive_binning
        self.binning_override = None
        # Saved states from before a series existed leave it out: it starts at its default.
        self.visible_series = {k: v["default_on"] for k, v in self.SERIES_CONFIG.items()}
        if visible_series:
            self.visible_series.update(visible_series)

        self.legend_hover_series = None
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.hover_avgs = {k: False for k in self.SERIES_CONFIG}
        self.avg_values = {k: 0.0 for k in self.SERIES_CONFIG}
        self.avg_visible = True
        self.avg_on_active_days = True
        self.cumulative_visible = True
        self.show_stats = True
        self.fit_to_data = False

        self._path_cache = {}
        self._margin_cache = None
        self._avg_val_cache = None
        self._labels_cache = None
        self._binned_data_cache = None
        self._scaffold_cache_key = None
        self._scaffold_cache_pixmap = None
        self._chrome_cache_key = None
        self._chrome_cache_pixmap = None
        self._calc_averages()

        data_length = 0
        for key in self.retention_data:
            if self.retention_data[key]:
                data_length = len(self.retention_data[key])
                break
        self.init_zoom(data_length)

        self.chart_opacity_pct = 100
        init_chart_widget_state(
            self,
            mouse_tracking=True,
            hover_attr="hover_index",
            hover_value=-1,
            tooltip=True,
            hide_tooltip=False,
            animation_kwargs={"duration": 600, "easing": QEasingCurve.Type.OutCubic},
        )
        self.avg_tooltips = {}
        for key in self.SERIES_CONFIG:
            self.avg_tooltips[key] = FloatingAvgLabel(self)
        self._data_transition_active = False
        self._data_transition_old_series = {}
        self._data_transition_new_series = {}
        self._data_transition_sample_count = 0
        self._data_transition_old_labels = []
        self._data_transition_old_display_data = {}
        self._data_transition_new_display_data = {}
        self._data_transition_render_cache = {}
        self._data_transition_old_range = (0.0, 100.0)
        self._data_transition_new_range = (0.0, 100.0)
        if hasattr(self, "animation"):
            self.animation.finished.connect(self._on_animation_finished)

    def _clear_data_transition_state(self):
        return clear_data_transition_state_impl(self)

    @property
    def binning_active(self):
        return binning_active_getter(self)

    def set_chart_opacity(self, pct):
        return set_chart_opacity_impl(self, pct)

    def set_average_mode(self, visible, on_active_days=True):
        return set_average_mode_impl(self, visible, on_active_days)

    def set_cumulative_mode(self, visible):
        return set_cumulative_mode_impl(self, visible)

    def set_show_stats(self, enabled):
        return set_show_stats_impl(self, enabled)

    def set_fit_to_data(self, enabled):
        return set_fit_to_data_impl(self, enabled)

    def set_min_reviews(self, value):
        """Hide the rate of points with fewer reviews than this (0 = show all)."""
        return set_min_reviews_impl(self, value)

    def series_totals(self):
        return series_totals_impl(self)

    def set_rounded(self, enabled):
        """Smooth the lines and round the top of the review bars."""
        self.rounded = bool(enabled)
        self._path_cache = {}
        self.update()

    def set_review_axis(self, enabled):
        """Show the review count labels on the right of the bars."""
        self.review_axis = bool(enabled)
        # The right margin changes, so the cached line paths have the wrong width.
        self._path_cache = {}
        self._chrome_cache_key = None
        self._scaffold_cache_key = None
        self.update()

    def set_review_bars(self, enabled):
        """Draw faint bars of the review count behind the lines."""
        from .bars import fade_to

        self.review_bars = bool(enabled)
        # The axis only counts while bars are on, so the margin may change here too.
        self._path_cache = {}
        self._chrome_cache_key = None
        self._scaffold_cache_key = None
        fade_to(self, self.review_bars)

    def get_data_range(self):
        return get_data_range_impl(self)

    def update_data(self, new_ret_data, adaptive_binning=None, transition=False, transition_duration_ms=220):
        return update_data_impl(
            self,
            new_ret_data,
            adaptive_binning=adaptive_binning,
            transition=transition,
            transition_duration_ms=transition_duration_ms,
        )

    def _on_animation_finished(self):
        return on_animation_finished_impl(self)

    def _extract_series_values(self, series_data):
        return extract_series_values_impl(self, series_data)

    def _sample_series_values(self, values, sample_count):
        return sample_series_values_impl(self, values, sample_count)

    def _prepare_data_transition(self, new_ret_data):
        return prepare_data_transition_impl(self, new_ret_data)

    def _draw_series_transition(self, painter, margin_left, margin_top, plot_w, plot_h, max_val, min_val=0):
        return draw_series_transition_impl(self, painter, margin_left, margin_top, plot_w, plot_h, max_val, min_val=min_val)

    def _get_display_data(self):
        return get_display_data_impl(self)

    def _compute_display_data(self, source_data):
        return compute_display_data_impl(self, source_data)

    def _get_display_n(self):
        return get_display_n_impl(self)

    def _invalidate_data_caches(self):
        return invalidate_data_caches_impl(self)

    def _calc_averages(self):
        return calc_averages_impl(self)

    def _avg_from_series_rows(self, series_rows, active_only):
        return avg_from_series_rows_impl(self, series_rows, active_only)

    def _avg_from_display_series(self, data):
        return avg_from_display_series_impl(self, data)

    def _get_series_avg_y(self, series_key, margin_top, plot_h, max_val, min_val=0):
        return get_series_avg_y_impl(self, series_key, margin_top, plot_h, max_val, min_val=min_val)

    def _get_series_avg_alpha(self, series_key):
        return get_series_avg_alpha_impl(self, series_key)

    def set_series_visible(self, series_key, visible):
        return set_series_visible_impl(self, series_key, visible)

    def _get_margin_right(self, font_metrics):
        return get_margin_right_impl(self, font_metrics)

    def mouseMoveEvent(self, event):
        return mouse_move_event_impl(self, event)

    def leaveEvent(self, event):
        return leave_event_impl(self, event)

    def hideEvent(self, event):
        return hide_event_impl(self, event)

    def changeEvent(self, event):
        return change_event_impl(self, event)

    def wheelEvent(self, event):
        return wheel_event_impl(self, event)

    def reset_zoom(self):
        return reset_zoom_impl(self)

    def mousePressEvent(self, event):
        return mouse_press_event_impl(self, event)

    def resizeEvent(self, event):
        return resize_event_impl(self, event)

    def set_zoom_range(self, start_idx, end_idx):
        return set_zoom_range_impl(self, start_idx, end_idx)

    def mouseReleaseEvent(self, event):
        return mouse_release_event_impl(self, event)

    def _apply_zoom_to_data(self):
        return apply_zoom_to_data_impl(self)

    def paintEvent(self, event):
        return paint_event_impl(self, event)

    def draw_bottom_stats(self, painter, plot_w, h, margin_left, margin_bottom):
        return draw_bottom_stats_impl(self, painter, plot_w, h, margin_left, margin_bottom)

    def get_stats_text(self):
        return get_stats_text_impl(self)
