# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import importlib

# Lazy exports (PEP 562). Importing every chart class here would load the whole chart stack
# at Anki startup, because main_menu.manager lives under this package. Names are imported on
# first access instead.
_LAZY_IMPORTS = {
    "HTMLDelegate": (".common", "HTMLDelegate"),
    "SparklineWidget": (".charts.common", "SparklineWidget"),
    "SegmentedBarWidget": (".charts.segmented_bar", "SegmentedBarWidget"),
    "BarChartWidget": (".charts.bar_chart", "BarChartWidget"),
    "ActivityChart": (".charts.activity", "ActivityChart"),
    "AddedChartWidget": (".charts.added_chart", "AddedChartWidget"),
    "ActivityStackedChart": (".charts.activity_stacked", "ActivityStackedChart"),
    "GroupedBarWidget": (".charts.grouped_bar", "GroupedBarWidget"),
    "PieChartWidget": (".charts.pie_chart", "PieChartWidget"),
    "RetentionChart": (".charts.retention", "RetentionChart"),
    "HeatmapWidget": (".charts.heatmap", "HeatmapWidget"),
    "StabilityChartWidget": (".charts.stability", "StabilityChartWidget"),
    "DifficultyChartWidget": (".charts.difficulty", "DifficultyChartWidget"),
    "RetrievabilityChartWidget": (".charts.retrievability", "RetrievabilityChartWidget"),
    "StatCardWidget": (".stats_cards", "StatCardWidget"),
    "StatCardsContainer": (".stats_cards", "StatCardsContainer"),
    "RowGroupedStatContainer": (".stats_cards", "RowGroupedStatContainer"),
    "HorizontalScrollTable": (".table", "HorizontalScrollTable"),
    "HourlyBreakdownChart": (".charts.hourly", "HourlyBreakdownChart"),
    "FutureDueChart": (".charts.future_due", "FutureDueChart"),
    "ReviewIntervalsChart": (".charts.review_intervals", "ReviewIntervalsChart"),
}


def __getattr__(name):
    target = _LAZY_IMPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_path, attr_name = target
    module = importlib.import_module(module_path, __name__)
    value = getattr(module, attr_name)
    # Cache on the module namespace so subsequent access is a normal, fast
    # attribute lookup instead of going through __getattr__ again.
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals().keys()) | set(_LAZY_IMPORTS.keys()))


__all__ = sorted(_LAZY_IMPORTS)
