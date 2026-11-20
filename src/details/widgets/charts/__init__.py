# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Chart widgets package. Re-exports all public chart classes, each imported when first asked for (PEP 562):
importing one module of the package (more_charts, a chart's data ops) no longer imports every Qt chart, which
froze Anki at its start (the web pinned block reads a list of more_charts there)."""

import importlib

_WHERE = {
    'AddedChartWidget': 'added_chart',
    'BarChartWidget': 'bar_chart',
    'DifficultyChartWidget': 'difficulty',
    'FSRSBaseChart': 'fsrs_base',
    'FutureDueChart': 'future_due',
    'GroupedBarWidget': 'grouped_bar',
    'HeatmapWidget': 'heatmap',
    'HourlyBreakdownChart': 'hourly',
    'ActivityChart': 'activity',
    'PieChartWidget': 'pie_chart',
    'RetentionChart': 'retention',
    'RetrievabilityChartWidget': 'retrievability',
    'ReviewIntervalsChart': 'review_intervals',
    'SegmentedBarWidget': 'segmented_bar',
    'StabilityChartWidget': 'stability',
    'ActivityStackedChart': 'activity_stacked',
}

__all__ = list(_WHERE)


def __getattr__(name):
    mod = _WHERE.get(name)
    if mod is None:
        raise AttributeError(name)
    value = getattr(importlib.import_module('.' + mod, __name__), name)
    globals()[name] = value
    return value
