# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Deep Dive stats runtime update helpers."""

from datetime import datetime

from aqt.qt import QLabel

from ....logic.data.transforms.heatmap_series import (
    build_heatmap_data,
    extract_heatmap_future_values,
    merge_heatmap_future_values,
)
from ... import Config
from .. import GroupedBarWidget, HeatmapWidget, HourlyBreakdownChart, log_debug
from ....widgets.stats_cards import (
    apply_dashboard_stat_values,
    build_dashboard_history_totals,
    build_dashboard_stat_values,
)
from ....logic.logger import log_error
from ....logic.logger import log_swallowed


def update_stats_from_history(self, history_slice):
    """Update stat cards based on a slice of history data."""
    log_debug(f"[STATS] _update_stats_from_history: len={len(history_slice) if history_slice else 0}", tag="DEEPDIVE")
    if not history_slice:
        return
    if getattr(self, "_dd_refresh_in_progress", False):
        return
    
    
    prec = self.dialog.addon_config.config.get(Config.STATS_PRECISION, 2)
    
    current_streak_text = None
    if hasattr(self, "streak_card") and self.streak_card and hasattr(self.streak_card, "value_lbl"):
        current_streak_text = self.streak_card.value_lbl.text()
    totals_payload = build_dashboard_history_totals(history_slice, streak_current=0)
    totals_payload.update(getattr(self, "_stats_state", None) or {})
    stat_values = build_dashboard_stat_values(
        totals_payload,
        use_decimal=True,
        hrs_unit="h",
        min_unit=" min",
        prec=prec,
    )
    if current_streak_text is not None:
        # Preserve previous streak display because history slice doesn't recalculate streak.
        stat_values["streak"] = current_streak_text
    apply_dashboard_stat_values(self.dialog, stat_values, refresh=True)

    dist_chart = None
    if hasattr(self, 'dist_chart') and self.dist_chart:
        dist_chart = self.dist_chart
    elif hasattr(self, 'section_wrappers') and "distribution" in self.section_wrappers:
         dist_wrapper = self.section_wrappers["distribution"]
         if hasattr(dist_wrapper, 'body_widget'):
             dist_chart = dist_wrapper.body_widget
    elif hasattr(self, 'dialog') and hasattr(self.dialog, 'expanded_chart_area'):
        for i in range(self.dialog.expanded_chart_area.count()):
            item = self.dialog.expanded_chart_area.itemAt(i)
            if item and item.widget():
                for w in item.widget().findChildren(GroupedBarWidget):
                    dist_chart = w
                    break
    
    if dist_chart and hasattr(dist_chart, 'update_data'):
        new_dist = {
            "learning": [0, 0, 0, 0],
            "young": [0, 0, 0, 0],
            "mature": [0, 0, 0, 0]
        }

        for h in history_slice:
            learning = h.get("learning_buttons", [])
            if learning and len(learning) == 4:
                for i in range(4): new_dist["learning"][i] += learning[i]

            young = h.get("young_buttons", [])
            if young and len(young) == 4:
                for i in range(4): new_dist["young"][i] += young[i]

            mature = h.get("mature_buttons", [])
            if mature and len(mature) == 4:
                for i in range(4): new_dist["mature"][i] += mature[i]

        try:
            dist_chart.update_data(new_dist)
        except (RuntimeError, AttributeError) as e:
            if "deleted" in str(e).lower() or "runtimeerror: wrapinstance" in str(e).lower():
                if hasattr(self, 'dist_chart'): self.dist_chart = None

    heatmap_chart = None
    if hasattr(self, 'heatmap_chart') and self.heatmap_chart:
        heatmap_chart = self.heatmap_chart
    elif hasattr(self, 'section_wrappers') and "heatmap" in self.section_wrappers:
         hm_wrapper = self.section_wrappers["heatmap"]
         if hasattr(hm_wrapper, 'body_widget'):
             heatmap_chart = hm_wrapper.body_widget
    elif hasattr(self, 'dialog') and hasattr(self.dialog, 'expanded_chart_area'):
        for i in range(self.dialog.expanded_chart_area.count()):
            item = self.dialog.expanded_chart_area.itemAt(i)
            if item and item.widget():
                for w in item.widget().findChildren(HeatmapWidget):
                    heatmap_chart = w
                    break
    
    if heatmap_chart:
        old_heatmap_data = getattr(heatmap_chart, "data", {}) or {}
        new_heatmap_data, _ = build_heatmap_data(history_slice)

        # Keep already visible future-due cells during sync updates. Zoom-driven
        # history slices carry no future counts, so without this the cells flicker out
        # and back.
        old_future_cells = extract_heatmap_future_values(old_heatmap_data)
        if old_future_cells:
            merge_heatmap_future_values(
                new_heatmap_data,
                old_future_cells,
                mode="max",
            )

        try:
            # The heatmap is updated once below, together with its window, so days
            # entering or leaving the zoomed range fade instead of popping.
            heatmap_applied = False
            
            if history_slice:
                latest_entry = history_slice[-1]
                try:
                    d_str = latest_entry.get("logical_date")
                    if d_str:
                        latest_dt = datetime.strptime(d_str, "%Y-%m-%d")
                        current_mode = getattr(heatmap_chart, "view_mode", "year")
                        # Follow the last day shown by the other charts (zoom end).
                        # A slice reaching the newest day means the full period.
                        anchor_day = latest_dt.date()
                        try:
                            full_hist = getattr(self, "last_history_data", None) or []
                            newest = max(
                                (str(h.get("logical_date") or "") for h in (full_hist[0], full_hist[-1])),
                                default="",
                            ) if full_hist else ""
                            range_last = getattr(self, "_dd_range_last_day", None)
                            if range_last is not None and newest and d_str[:10] >= newest[:10]:
                                anchor_day = range_last
                        except Exception:
                            log_swallowed()
                        from ..runtime.heatmap_anchor import resolve_heatmap_state

                        self.heatmap_year, self.end_date_365, target_end = resolve_heatmap_state(
                            self, current_mode, anchor_day, now=datetime.now()
                        )
                        heatmap_chart.transition_to(new_heatmap_data, target_end)
                        heatmap_applied = True
                        parent = heatmap_chart.parentWidget()
                        if parent:
                            year_lbl = parent.findChild(QLabel, "heatmap_year_lbl")
                            if year_lbl:
                                year_lbl.setText(str(self.heatmap_year))
                except ValueError:
                    pass
            if not heatmap_applied:
                heatmap_chart.update_data(new_heatmap_data)
                    
        except (RuntimeError, AttributeError):
            # Silently handle UI sync issues during transitions
            pass

    hourly_chart = None
    if hasattr(self, 'section_wrappers') and "hourly" in self.section_wrappers:
        hourly_wrapper = self.section_wrappers["hourly"]
        if hasattr(hourly_wrapper, 'body_widget'):
            hourly_chart = hourly_wrapper.body_widget
    elif hasattr(self, 'dialog') and hasattr(self.dialog, 'expanded_chart_area'):
        for i in range(self.dialog.expanded_chart_area.count()):
            item = self.dialog.expanded_chart_area.itemAt(i)
            if item and item.widget():
                for w in item.widget().findChildren(HourlyBreakdownChart):
                    hourly_chart = w
                    break
    
    if hourly_chart and hasattr(hourly_chart, 'update_data'):
        try:
            # Aggregate hourly data from the history_slice cache, which holds pre-computed hourly distributions per day/bin.
            aggregated_hourly = {h: {"total": 0, "correct": 0} for h in range(24)}
            
            for h_bin in history_slice:
                b_hourly = h_bin.get("hourly")
                if b_hourly:
                    for h in range(24):
                        if h in b_hourly:
                            aggregated_hourly[h]["total"] += b_hourly[h].get("total", 0)
                            aggregated_hourly[h]["correct"] += b_hourly[h].get("correct", 0)
                else:
                    # Fallback for adaptive zoom: the 10-minute bins have no hourly dict, but they
                    # do have a "YYYY-MM-DD HH:MM" date string.
                    d_str = h_bin.get("date", "")
                    if " " in d_str:
                        try:
                            hour_part = d_str.split(" ")[1].split(":")[0]
                            h = int(hour_part)
                            if 0 <= h < 24:
                                aggregated_hourly[h]["total"] += h_bin.get("reviews", 0)
                                aggregated_hourly[h]["correct"] += h_bin.get("passed", 0)
                        except (IndexError, ValueError):
                            pass
            
            hourly_chart.update_data(aggregated_hourly)
        except Exception as e:
            log_error(f"Failed to update hourly chart from cache on zoom: {e}")

    # Update Future Due and Review Intervals if in adaptive view
    # (These normally rely on PinnedDataManager/Cache which might not follow sub-day zoom)
    is_adaptive = " " in history_slice[0].get("date", "") if history_slice else False
    if is_adaptive:
        # Future Due and Review Intervals deal with future data or non-temporal distributions, so they cannot be sliced from history_slice; just refresh them so they stay visible.
        pass

def update_dashboard_visibility(self):
    """Update visibility of stat cards (delegated to main dialog)."""
    if hasattr(self, 'dialog'):
        self.dialog.update_dashboard_visibility()








