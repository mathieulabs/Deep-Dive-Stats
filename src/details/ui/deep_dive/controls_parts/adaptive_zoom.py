# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ... import rollover_hour
from .. import log_debug
from ....animations.chart_policy import local_chart_animation_batch
from ....logic.data.section_fetchers import fetch_section_data
from ....logic.data.transforms.retention_series import (
    RETENTION_SERIES_KEYS,
    build_retention_series,
)
from ....widgets.charts.common.zoom import (
    build_adaptive_fetch_bounds,
    compute_transition_align_right,
    resolve_adaptive_zoom_window,
)
from ....logic.logger import log_swallowed


def try_adaptive_zoom(manager, zoomed_slice, source_chart=None, start_idx=None, end_idx=None):
    """Attempt adaptive re-binning when zoom range is very small."""
    try:
        if not zoomed_slice or len(zoomed_slice) < 2:
            if getattr(manager, "_adaptive_zoom_active_added_only", False):
                manager._restore_original_chart_data(only_added=True)
                manager._adaptive_zoom_active_added_only = False
                manager.update_all_reset_buttons()
            elif manager._adaptive_zoom_active:
                manager._restore_original_chart_data()
                manager._adaptive_zoom_active = False
                manager.update_all_reset_buttons()
            return

        zoom_window = resolve_adaptive_zoom_window(zoomed_slice, date_keys=("logical_date", "date"))
        if zoom_window:
            if manager._adaptive_zoom_active or getattr(manager, "_adaptive_zoom_active_added_only", False):
                return

            source_len = int(getattr(source_chart, "_full_length", 0) or 0) if source_chart else 0
            manager._adaptive_zoom_transition_align_right = compute_transition_align_right(
                start_idx=start_idx,
                end_idx=end_idx,
                source_len=source_len,
                default=True,
            )

            offset_s = rollover_hour() * 3600
            start_ms, end_ms = build_adaptive_fetch_bounds(
                zoom_window["first_dt"],
                zoom_window["last_dt"],
                offset_seconds=offset_s,
            )

            row_data = manager.last_row_data
            if not row_data:
                return

            target_did = row_data.get("did")
            is_deleted = row_data.get("is_deleted", False)

            hi_res_history = fetch_section_data(
                manager.addon_config,
                "reviews",
                deck_id=target_did,
                is_deleted=is_deleted,
                override_start_ms=start_ms,
                override_end_ms=end_ms,
                override_bin_ms=600000,
            )

            hi_res_added = None
            if hasattr(manager, "added_chart") and manager.added_chart:
                hi_res_added = fetch_section_data(
                    manager.addon_config,
                    "added",
                    deck_id=target_did,
                    is_deleted=is_deleted,
                    override_start_ms=start_ms,
                    override_end_ms=end_ms,
                    override_bin_ms=600000,
                )

            if not hi_res_history and not hi_res_added:
                return

            is_added_chart = source_chart and source_chart == getattr(manager, "added_chart", None)
            has_reviews = False
            if hi_res_history:
                has_reviews = any(item.get("reviews", 0) > 0 for item in hi_res_history)

            if not has_reviews and is_added_chart:
                manager._pre_adaptive_zoom = ("added", int(start_idx or 0), int(end_idx or 0))
                log_debug(
                    f"[ADAPTIVE-ADDED-ONLY] Activated: range={start_ms}-{end_ms}",
                    tag="DEEPDIVE",
                )
                with local_chart_animation_batch(manager.added_chart):
                    manager._adaptive_transitioning = True
                    try:
                        if hi_res_added:
                            manager._adaptive_replace(manager.added_chart, "_full_data", hi_res_added)
                    finally:
                        manager._adaptive_transitioning = False
                manager._adaptive_zoom_active_added_only = True
                manager.update_all_reset_buttons()
                return

            if not hi_res_history:
                return

            log_debug(
                f"[ADAPTIVE] Activated: len={len(hi_res_history)}, range={start_ms}-{end_ms}",
                tag="DEEPDIVE",
            )

            total_len = len(manager.last_history_data or [])
            offset = total_len - (source_len or total_len)
            manager._pre_adaptive_zoom = ("history", int(start_idx or 0) + offset, int(end_idx or 0) + offset)
            manager._hi_res_history = hi_res_history
            from ....logic.data.transforms.activity_series import filter_activity_types

            hi_res_activity_rows = filter_activity_types(
                hi_res_history, manager._get_dd_widget_setting("activity", "hidden_review_types", None)
            )
            hi_res_activity = [(item["pretty_date"], item["reviews"]) for item in hi_res_activity_rows]
            adaptive_candidates = [
                manager.activity_chart,
                manager.stacked_chart,
                manager.retention_chart,
                getattr(manager, "added_chart", None),
            ]
            with local_chart_animation_batch(source_chart or manager.activity_chart, candidates=adaptive_candidates):
                manager._adaptive_transitioning = True
                try:
                    manager._adaptive_replace(manager.activity_chart, "_full_data", hi_res_activity)
                    manager._adaptive_replace(manager.stacked_chart, "_full_data", hi_res_activity_rows)

                    if manager.retention_chart:
                        hi_res_retention = build_retention_series(
                            hi_res_history,
                            strict_series=RETENTION_SERIES_KEYS,
                        )
                        manager._adaptive_replace(
                            manager.retention_chart,
                            "_full_retention_data",
                            hi_res_retention,
                        )

                    if hi_res_added:
                        manager._adaptive_replace(manager.added_chart, "_full_data", hi_res_added)
                finally:
                    manager._adaptive_transitioning = False

            manager._update_stats_from_history(hi_res_history)
            manager._adaptive_zoom_active = True
            manager.update_all_reset_buttons()
        else:
            if getattr(manager, "_adaptive_zoom_active_added_only", False):
                manager._restore_original_chart_data(only_added=True)
                manager._adaptive_zoom_active_added_only = False
                manager.update_all_reset_buttons()
            elif manager._adaptive_zoom_active:
                manager._restore_original_chart_data()
                manager._adaptive_zoom_active = False
                manager.update_all_reset_buttons()
    except Exception:
        log_swallowed()

