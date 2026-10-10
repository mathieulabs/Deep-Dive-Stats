# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
# Shared deep-dive imports exposed at package level to avoid a dedicated deps module.
from ...logic import log_debug, log_info
from ...logic.history_provider import HistoryProvider
from ...logic.metrics import (
    FutureDueDataProvider,
    HourlyDataProvider,
    ReviewIntervalsDataProvider,
)
from ...widgets import (
    ActivityChart,
    FutureDueChart,
    HeatmapWidget,
    HourlyBreakdownChart,
    ReviewIntervalsChart,
)
from ...widgets.charts.added_chart import AddedChartWidget
from ...widgets.charts.grouped_bar import GroupedBarWidget
from ...widgets.chart_utils.theme import get_theme_colors
from ...widgets.charts.activity_stacked import ActivityStackedChart
from ...widgets.charts.retention import RetentionChart
from ...widgets.common import AdaptiveStatsWidget
# Keep this import last: manager imports deep_dive submodules that rely on exports above.
from .manager import DeepDiveManager

__all__ = [
    "ActivityChart",
    "ActivityStackedChart",
    "AdaptiveStatsWidget",
    "DeepDiveManager",
    "FutureDueChart",
    "FutureDueDataProvider",
    "HeatmapWidget",
    "HistoryProvider",
    "GroupedBarWidget",
    "HourlyBreakdownChart",
    "HourlyDataProvider",
    "ReviewIntervalsChart",
    "ReviewIntervalsDataProvider",
    "RetentionChart",
    "AddedChartWidget",
    "get_theme_colors",
    "log_debug",
    "log_info",
]
