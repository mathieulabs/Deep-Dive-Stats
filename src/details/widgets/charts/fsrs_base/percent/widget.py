# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .. import FSRSBaseChart
from .shared import (
    draw_fsrs_percent_bars,
    draw_fsrs_percent_extras,
    load_fsrs_gradient_colors,
    mouse_move_fsrs_percent_chart,
    refresh_fsrs_gradient_colors,
)


class FSRSPercentChartBase(FSRSBaseChart):
    chart_title = ""
    reverse_gradient = False
    exact_hover_match = False
    clear_hover_outside_plot = False

    def __init__(self, data_dict, parent=None, adaptive_binning=True):
        super().__init__(data_dict, self.chart_title, parent, adaptive_binning=adaptive_binning)
        self.show_cumulative_axis = False
        self._chrome_cache_key = None
        self._chrome_cache_pixmap = None
        self._bar_color_cache_key = None
        self._bar_color_cache = None
        self._load_gradient_colors()

    def _load_gradient_colors(self):
        return load_fsrs_gradient_colors(self)

    def refresh_data_colors(self):
        return refresh_fsrs_gradient_colors(self)

    def mouseMoveEvent(self, event):
        return mouse_move_fsrs_percent_chart(
            self,
            event,
            exact_match=self.exact_hover_match,
            clear_outside_plot=self.clear_hover_outside_plot,
        )

    def draw_bars(self, painter, plot_w, plot_h, margin_left, margin_top):
        return draw_fsrs_percent_bars(
            self,
            painter,
            plot_w,
            plot_h,
            margin_left,
            margin_top,
            reverse_gradient=self.reverse_gradient,
        )

    def draw_extras(self, painter, plot_w, plot_h, margin_left, margin_top, margin_bottom, w, h):
        return draw_fsrs_percent_extras(self, painter, plot_w, margin_left, margin_bottom, h)
