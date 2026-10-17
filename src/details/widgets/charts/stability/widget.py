# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QColor

from .data_ops import (
    build_binned_values_impl,
    compute_median_impl,
    current_values_snapshot_impl,
    get_margins_impl,
    get_stats_text_impl,
    get_tooltip_text_impl,
    init_state_impl,
    refresh_data_colors_impl,
    set_cumulative_mode_impl,
    set_view_filter_impl,
    update_data_impl,
)
from .render_ops import draw_bars_impl, draw_extras_impl, paint_event_impl
from ..fsrs_base import FSRSBaseChart


class StabilityChartWidget(FSRSBaseChart):
    def __init__(self, data_dict, parent=None, adaptive_binning=True):
        super().__init__(data_dict, "Stability", parent, adaptive_binning=adaptive_binning)
        from ....ui import Config, get_chart_color

        self.color = QColor(get_chart_color(Config.COLOR_BAR, self))
        init_state_impl(self)
        self._compute_median()

    def _get_margins(self):
        return get_margins_impl(self)

    def set_cumulative_mode(self, visible):
        return set_cumulative_mode_impl(self, visible)

    def _compute_median(self):
        return compute_median_impl(self)

    def refresh_data_colors(self):
        return refresh_data_colors_impl(self)

    def update_data(self, new_data_dict, adaptive_binning=None, transition_mode=None):
        return update_data_impl(self, new_data_dict, adaptive_binning=adaptive_binning, transition_mode=transition_mode)

    def _build_binned_values(self, dist, max_days):
        return build_binned_values_impl(self, dist, max_days)

    def _current_values_snapshot(self):
        return current_values_snapshot_impl(self)

    def set_view_filter(self, filter_mode, transition_mode=None):
        return set_view_filter_impl(self, filter_mode, transition_mode=transition_mode)

    def draw_bars(self, painter, plot_w, plot_h, margin_left, margin_top):
        return draw_bars_impl(self, painter, plot_w, plot_h, margin_left, margin_top)

    def paintEvent(self, event):
        return paint_event_impl(self, event)

    def draw_extras(self, painter, plot_w, plot_h, margin_left, margin_top, margin_bottom, w, h):
        return draw_extras_impl(self, painter, plot_w, plot_h, margin_left, margin_top, margin_bottom, w, h)

    def get_stats_text(self):
        return get_stats_text_impl(self)

    def get_tooltip_text(self, k, v):
        return get_tooltip_text_impl(self, k, v)
