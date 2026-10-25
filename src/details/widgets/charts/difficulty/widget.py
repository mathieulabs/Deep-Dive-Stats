# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .data_ops import get_stats_text_impl, get_tooltip_text_impl
from ..fsrs_base.percent import FSRSPercentChartBase


class DifficultyChartWidget(FSRSPercentChartBase):
    chart_title = "Difficulty"
    reverse_gradient = True
    exact_hover_match = True
    clear_hover_outside_plot = True

    def get_stats_text(self):
        return get_stats_text_impl(self)

    def get_tooltip_text(self, k, v):
        return get_tooltip_text_impl(self, k, v)
