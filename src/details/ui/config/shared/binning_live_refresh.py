# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations

from typing import TYPE_CHECKING

from ... import ADAPTIVE_CHART_BINNING
from ....logic.logger import log_swallowed

if TYPE_CHECKING:
    from ..dialogs.tabs_config_dialog import DetailedStatsConfigDialog


def refresh_binning_live(dialog: "DetailedStatsConfigDialog") -> None:
    """Apply binning changes immediately to visible charts (details + pinned)."""
    try:
        from ....widgets.chart_utils.binning import invalidate_binning_level_cache

        invalidate_binning_level_cache()
    except Exception:
        log_swallowed()

    try:
        ddm = getattr(dialog.parent_dialog, "deep_dive_manager", None)
        if ddm is not None:
            adaptive = bool(dialog.parent_dialog.addon_config.config.get(ADAPTIVE_CHART_BINNING, True))
            all_chart_attrs = [
                "activity_chart",
                "stacked_chart",
                "retention_chart",
                "added_chart",
                "stability_chart",
                "difficulty_chart",
                "retrievability_chart",
                "future_due_chart",
                "review_intervals_chart",
            ]
            for attr in all_chart_attrs:
                chart = getattr(ddm, attr, None)
                if not chart:
                    continue
                if hasattr(chart, "adaptive_binning"):
                    chart.adaptive_binning = adaptive
                if hasattr(chart, "update_data"):
                    try:
                        if hasattr(chart, "_full_retention_data"):
                            chart.update_data(
                                chart._full_retention_data or chart.retention_data,
                                adaptive_binning=adaptive,
                                transition=False,
                            )
                        elif hasattr(chart, "data_dict"):
                            chart.update_data(
                                chart.data_dict, adaptive_binning=adaptive, transition_mode=None
                            )
                        elif hasattr(chart, "data"):
                            chart.update_data(
                                chart.data, adaptive_binning=adaptive, transition_mode=None
                            )
                        else:
                            raise RuntimeError("No known source payload")
                    except Exception:
                        if hasattr(chart, "_invalidate_data_caches"):
                            chart._invalidate_data_caches()
                        elif hasattr(chart, "_invalidate_caches"):
                            chart._invalidate_caches()
                        chart.update()
                else:
                    chart.update()
            try:
                if hasattr(ddm, "_refresh_bottom_stats"):
                    ddm._refresh_bottom_stats()
            except Exception:
                log_swallowed()
    except Exception:
        log_swallowed()

    try:
        from ....widgets.pinned.main_menu.manager import MainMenuWidgetManager

        if MainMenuWidgetManager.instance_exists():
            mgr = MainMenuWidgetManager.instance()
            mgr._widget_update_signatures.clear()
            mgr.refresh(clear_cache=False)
    except Exception:
        log_swallowed()

