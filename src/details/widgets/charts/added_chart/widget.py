# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QSizePolicy

from ..activity_stacked import ActivityStackedChart
from .data_ops import normalize_rows_impl, stats_text_impl


class AddedChartWidget(ActivityStackedChart):
    """Added chart powered by the same transition/render pipeline as ActivityStackedChart."""

    _SERIES_CONFIG = [{"key": "count", "label": "Added", "color": "#669ff7"}]

    def __init__(self, data, parent=None, adaptive_binning=True):
        from ....ui import Config, get_chart_color

        series_config = [{"key": "count", "label": "Added", "color": get_chart_color(Config.COLOR_BAR, parent)}]
        super().__init__(
            self._normalize_rows(data),
            series_config,
            parent=parent,
            adaptive_binning=adaptive_binning,
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(220)
        self.cumulative_visible = True
        self.avg_visible = True
        self.avg_on_active_days = True
        self.show_hover_marker = False
        self._relative_height_transition = False
        self._intensity_by_value_coloring = True
        self._bar_width_ratio = 0.95

    def refresh_data_colors(self):
        from ....ui import Config, get_chart_color

        if self.series_config:
            self.series_config[0]["color"] = get_chart_color(Config.COLOR_BAR, self)

    @staticmethod
    def _normalize_rows(rows):
        return normalize_rows_impl(rows)

    def update_data(
        self,
        new_data,
        adaptive_binning=None,
        transition_mode=None,
        transition_align_right=None,
    ):
        super().update_data(
            self._normalize_rows(new_data),
            adaptive_binning=adaptive_binning,
            transition_mode=transition_mode,
            transition_align_right=transition_align_right,
        )

    def get_stats_text(self):
        return stats_text_impl(self)
