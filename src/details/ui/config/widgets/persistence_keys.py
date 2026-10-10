# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from __future__ import annotations

from ... import Config

WIDGET_BEHAVIOR_KEYS = (
    "show_average",
    "show_cumulative",
    "avg_on_active_days",
    "chart_opacity",
    "line_opacity",
    "bar_gradient",
    "show_grid",
    "show_legend",
    "legend_mode",
    "tooltip_hidden",
    "template",
    "radio_ranges",
    "filter_modes",
)

PINNED_UNLINK_STYLE_KEYS = (
    Config.FACECARDS_SCALE,
    Config.FACECARDS_TITLE_SIZE,
    Config.FACECARDS_TITLE_COLOR,
    Config.FACECARDS_SHOW_GLASS,
    Config.FACECARDS_GLASS_INTENSITY,
    Config.FACECARDS_GLASS_BLUR,
    Config.FACECARDS_GLASS_BORDER,
    Config.FACECARDS_HOVER_EFFECT,
    Config.FACECARDS_INLINE_STATS,
    Config.FACECARDS_TITLE_SHADOW_INTENSITY,
    Config.FACECARDS_STAT_SHADOW_INTENSITY,
    Config.HEATMAP_SCALE,
    Config.HEATMAP_NAV_POS,
    Config.HEATMAP_HIDE_TITLE,
    Config.HEATMAP_HIDE_LABELS,
    Config.HEATMAP_SHOW_LEGEND,
    Config.HEATMAP_SHOW_FUTURE,
    Config.HEATMAP_TINTED_FUTURE,
    Config.HEATMAP_ROUNDING,
    Config.HEATMAP_MONDAY_FIRST,
    Config.HEATMAP_COLOR,
    Config.HEATMAP_EMPTY_OPACITY,
    Config.HEATMAP_FILLED_OPACITY,
    Config.HEATMAP_VIBRANCE,
    Config.HEATMAP_INTENSITY_CURVE,
    Config.HEATMAP_EMPTY_WHITE,
    Config.HEATMAP_SHOW_GLASS,
    Config.HEATMAP_GLASS_INTENSITY,
    Config.HEATMAP_GLASS_BLUR,
    Config.HEATMAP_GLASS_BORDER,
    Config.HEATMAP_SHOW_CONTINUOUS_MODE,
    Config.HEATMAP_SHOW_365_MODE,
    Config.HEATMAP_SHOW_YEAR_MODE,
    Config.HEATMAP_TOOLTIP_HIDDEN,
    Config.PINNED_GLASS,
    Config.PINNED_GLASS_INTENSITY,
    Config.PINNED_GLASS_BLUR,
    Config.PINNED_GLASS_BORDER,
    Config.PINNED_HOVER_BORDER,
    Config.TEXT_WIDGET_SHOW_GLASS,
    Config.TEXT_WIDGET_GLASS_INTENSITY,
    Config.TEXT_WIDGET_GLASS_BLUR,
    Config.TEXT_WIDGET_GLASS_BORDER,
    Config.TEXT_WIDGET_HOVER_BORDER,
)

DASHBOARD_UNLINK_STYLE_KEYS = (
    Config.DASHBOARD_SCALE,
    Config.DASHBOARD_TITLE_SIZE,
    Config.DASHBOARD_SHOW_GLASS,
    Config.DASHBOARD_GLASS_INTENSITY,
    Config.DASHBOARD_GLASS_BORDER,
    Config.DASHBOARD_HOVER_EFFECT,
    Config.DASHBOARD_INLINE_STATS,
    Config.DASHBOARD_TITLE_SHADOW_INTENSITY,
    Config.DASHBOARD_STAT_SHADOW_INTENSITY,
)

DEEP_DIVE_STYLE_MARKER_KEYS = ("Pinned_Glass", "glass_intensity", "glass_border", "show_glass")

