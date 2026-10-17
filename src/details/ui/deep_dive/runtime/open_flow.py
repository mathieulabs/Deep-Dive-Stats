# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import re
import time

from aqt import mw
from aqt.qt import QLabel

from ... import Config
from ....logic.data.context_payloads import context_stats
from ....logic.logger import log_swallowed


def open_deep_dive(manager, deck_identifier, title, period_range=None):
    """Open the statistics dashboard for a deck or period."""
    manager._perf_start_time = time.time()

    manager._init_theme_vars()
    manager.last_scroll_value = manager.dialog.expanded_scroll.verticalScrollBar().value()

    is_same_layout_mode = True
    if hasattr(manager, "last_viewed_grid_mode"):
        is_same_layout_mode = manager.last_viewed_grid_mode == manager.grid_mode

    queue_in_progress = bool(getattr(manager, "_build_queue_active", False))
    skeleton_in_progress = bool(getattr(manager, "_is_skeleton", False))
    has_activity_chart = bool(manager.activity_chart)
    needs_full_rebuild = (
        (not has_activity_chart)
        or (not is_same_layout_mode)
        or queue_in_progress
        or skeleton_in_progress
    )
    manager.last_viewed_grid_mode = manager.grid_mode

    if needs_full_rebuild:
        manager._cleanup_previous_view()

    if deck_identifier is not None:
        manager.dialog.target_deck_id = deck_identifier
    if period_range is not None:
        manager.dialog.target_time_span = period_range

    raw_clean = manager._clean_title(title).split("//")[-1].strip()
    deck_name = re.sub(r"\s*\(.*?\)$", "", raw_clean)

    span_label = ""
    if period_range is not None:
        from ... import Period
        from ....logic.tabs import get_tabs_config

        tabs_config = get_tabs_config(manager.addon_config)
        for tab_conf in tabs_config:
            if tab_conf.get("range") == period_range:
                if period_range == Period.CUSTOM:
                    pass
                span_label = tab_conf.get("title", "")
                break
        if not span_label:
            span_label = Period.LABEL.get(period_range, "")
        if not span_label:
            span_label = str(period_range).capitalize()

    if span_label:
        display_title = f"{deck_name} ({span_label})".upper()
    else:
        display_title = deck_name.upper()

    manager.dialog.expanded_title.setText(display_title)

    if deck_identifier == "Deleted Cards" or "DELETED CARDS" in display_title:
        manager.last_pie_del = True
    else:
        manager.last_pie_del = manager.addon_config.config.get(Config.PIE_CHART_SHOW_DELETED, False)

    row_data = manager._find_row_data(deck_identifier, title, period_range)
    if not row_data:
        manager.dialog.expanded_chart_area.addWidget(
            QLabel(f"No detailed data found for '{title}'.", parent=manager.dialog)
        )
        manager.dialog.expanded_container.setVisible(True)
        if hasattr(manager.dialog, "layout_toggle_container"):
            manager.dialog.layout_toggle_container.setVisible(True)
        if hasattr(manager.dialog, "deck_select_btn"):
            manager.dialog.deck_select_btn.setVisible(True)
            manager.dialog.span_select_btn.setVisible(True)
        return

    requested_range = period_range if period_range is not None else manager.last_history_range
    current_range = manager.last_period_range if manager.last_period_range is not None else manager.last_history_range
    is_global_timespan_change = (
        not needs_full_rebuild
        and str(manager.last_deck_identifier) == str(deck_identifier)
        and str(current_range) != str(requested_range)
    )
    same_target = (
        not needs_full_rebuild
        and manager.dialog.expanded_container.isVisible()
        and str(manager.last_deck_identifier) == str(deck_identifier)
        and str(current_range) == str(requested_range)
    )
    if same_target:
        return

    try:
        from ...details_dialog.table_drawer import collapse_after_pick

        collapse_after_pick(manager.dialog)
    except Exception:
        log_swallowed()

    should_play_open_reveal = bool(
        needs_full_rebuild and not bool(getattr(manager, "_deep_dive_real_view_shown", False))
    )
    manager._defer_deep_dive_chart_reveal = should_play_open_reveal

    manager.dialog.expanded_container.setVisible(True)
    if hasattr(manager.dialog, "layout_toggle_container"):
        manager.dialog.layout_toggle_container.setVisible(True)
    if hasattr(manager.dialog, "deck_select_btn"):
        manager.dialog.deck_select_btn.setVisible(True)
        manager.dialog.span_select_btn.setVisible(True)

    manager._loading_seq += 1
    current_seq = manager._loading_seq

    captured_row_data = row_data
    captured_deck_id = deck_identifier
    captured_period = period_range

    target_did, history_range, is_deleted, added_sync, custom_days, custom_type, start_date_str, end_date_str = (
        manager._prepare_history_params(captured_row_data, captured_deck_id, captured_period)
    )
    from .heatmap_anchor import range_last_day

    manager._dd_range_last_day = range_last_day(
        history_range, custom_days, custom_type, start_date_str, end_date_str
    )


    if is_deleted:
        cache_did = -1
    elif isinstance(captured_row_data, dict) and captured_row_data.get("is_total_row"):
        cache_did = target_did if (manager.dialog.view_mode == "deck" and target_did is not None) else None
    elif target_did is not None:
        cache_did = target_did
    else:
        cache_did = captured_row_data.get("full_name") if isinstance(captured_row_data, dict) else None

    from ... import Period as _Period
    from ....widgets.pinned.context_access import get_pinned_context

    if history_range in [_Period.TODAY, _Period.YESTERDAY]:
        cached_ctx = None
    else:
        cached_ctx = get_pinned_context(
            cache_did,
            history_range,
            cfg=manager.addon_config,
            custom_days=custom_days,
            custom_type=custom_type,
            start_date_str=start_date_str,
            end_date_str=end_date_str,
        )

    if cached_ctx:
        manager._is_skeleton = False

        stats = context_stats(cached_ctx)
        stat_map = {
            "total_reviews": "reviews",
            "total_time_ms": "time_ms",
            "total_passed": "passed",
            "rev_young": "rev_young",
            "pass_young": "pass_young",
            "rev_mat": "rev_mat",
            "pass_mat": "pass_mat",
            "active_days": "active_days",
            "current_streak": "streak_current",
        }
        if stats:
            for src_k, dst_k in stat_map.items():
                if src_k in stats:
                    captured_row_data[dst_k] = stats[src_k]

        if "current_streak" in cached_ctx:
            captured_row_data["streak_current"] = cached_ctx["current_streak"]
        elif "streak" in stats:
            captured_row_data["streak_current"] = stats["streak"]

        manager.last_row_data = captured_row_data
        manager.last_history_data = cached_ctx.get("reviews", [])
        manager.last_history_context = cached_ctx
        manager.last_history_range = history_range
        manager.last_deck_identifier = captured_deck_id
        manager.last_period_range = captured_period
        try:
            manager.last_tab_index = int(manager.dialog.tab_widget.currentIndex())
        except Exception:
            manager.last_tab_index = None
        manager.last_title = title

        if hasattr(manager.dialog, "grid_view_btn"):
            manager.dialog.grid_view_btn.setVisible(True)
            manager.dialog.grid_view_btn.setChecked(manager.grid_mode)

        if needs_full_rebuild:
            manager._populate_dashboard()
            manager._setup_zoom_sync()
        else:
            manager._dd_refresh_reason = "time_span" if is_global_timespan_change else None
            try:
                manager._refresh_dashboard_data()
            finally:
                manager._dd_refresh_reason = None

        manager.dialog.stats_container.setVisible(True)
        manager.dialog.update_dashboard_visibility()
        return


    replace_skeleton_with_real = bool(needs_full_rebuild)
    if needs_full_rebuild:
        manager.last_history_data = []
        manager.last_row_data = row_data
        manager.last_deck_identifier = deck_identifier
        manager.last_title = title
        manager._is_skeleton = True

        manager._populate_dashboard(is_warmup=False)
        manager._setup_zoom_sync()
        needs_full_rebuild = False
    else:
        manager._is_skeleton = False
        manager._setup_zoom_sync()

    def bg_task():
        """Runs on a background thread - pure SQL, no UI access."""
        bg_started_at = time.perf_counter()
        history_data, history_range_, history_ctx = manager._fetch_history_bg(
            target_did,
            history_range,
            is_deleted,
            added_sync,
            custom_days=custom_days,
            custom_type=custom_type,
            start_date_str=start_date_str,
            end_date_str=end_date_str,
        )
        bg_elapsed_ms = (time.perf_counter() - bg_started_at) * 1000.0
        return history_data, history_range_, history_ctx, bg_elapsed_ms

    def on_done(future):
        """Runs on the main thread after bg_task completes."""
        if current_seq != manager._loading_seq:
            return

        manager._is_skeleton = False

        try:
            history_data, history_range_, history_ctx, bg_elapsed_ms = future.result()
        except Exception:
            manager.dialog.expanded_chart_area.addWidget(
                QLabel("Error loading data.", parent=manager.dialog)
            )
            return

        stats = context_stats(history_ctx)
        stat_map = {
            "total_reviews": "reviews",
            "total_time_ms": "time_ms",
            "total_passed": "passed",
            "rev_young": "rev_young",
            "pass_young": "pass_young",
            "rev_mat": "rev_mat",
            "pass_mat": "pass_mat",
            "active_days": "active_days",
            "current_streak": "streak_current",
        }
        if stats:
            for src_k, dst_k in stat_map.items():
                if src_k in stats:
                    captured_row_data[dst_k] = stats[src_k]

        if "current_streak" in history_ctx:
            captured_row_data["streak_current"] = history_ctx["current_streak"]
        elif "streak" in stats:
            captured_row_data["streak_current"] = stats["streak"]

        manager.last_row_data = captured_row_data
        manager.last_history_data = history_data
        manager.last_history_context = history_ctx
        manager.last_history_range = history_range_
        manager.last_deck_identifier = captured_deck_id
        manager.last_period_range = captured_period
        try:
            manager.last_tab_index = int(manager.dialog.tab_widget.currentIndex())
        except Exception:
            manager.last_tab_index = None

        if hasattr(manager.dialog, "grid_view_btn"):
            manager.dialog.grid_view_btn.setVisible(True)
            manager.dialog.grid_view_btn.setChecked(manager.grid_mode)

        if replace_skeleton_with_real:
            manager._defer_deep_dive_chart_reveal = not bool(
                getattr(manager, "_deep_dive_real_view_shown", False)
            )
            manager._populate_dashboard()
            manager._setup_zoom_sync()
        else:
            manager._defer_deep_dive_chart_reveal = False
            manager._dd_refresh_reason = "time_span" if is_global_timespan_change else None
            try:
                manager._refresh_dashboard_data()
            finally:
                manager._dd_refresh_reason = None

    mw.taskman.run_in_background(bg_task, on_done)

