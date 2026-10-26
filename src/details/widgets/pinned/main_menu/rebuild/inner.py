# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QTimer

from ..imports import mw
from .charts_layout import prepare_charts_layout
from .charts_prelude import prepare_other_defs_and_reflow
from .charts_widgets import rebuild_charts_widgets
from ..block_order import apply_block_layout_order
from .deck_prewarm import prewarm_deck_data
from .defs import collect_pinned_defs, handle_empty_pinned_defs, remove_stale_widgets
from .finalize import finalize_rebuild, show_overlay
from .overlay_state import ensure_overlay_and_rebuild_mode, reset_layout_for_full_rebuild
from .prelude import (
    build_current_state,
    compute_rebuild_modes,
    defer_if_global_cache_uninitialized,
    resolve_max_ids,
    run_incremental_cache_refresh,
    strip_main_layout_spacers,
)
from .stat_cards import rebuild_stat_cards
from .....logic.logger import log_swallowed


def rebuild_overlay_inner(manager, deck_id):
    (
        non_blocking_update,
        overview_light_mode,
        review_return_light_mode,
        review_return_phase_b_mode,
    ) = compute_rebuild_modes(manager, deck_id)
    strip_main_layout_spacers(manager)
    max_ids = resolve_max_ids(manager, deck_id)
    if max_ids is None:
        return
    run_incremental_cache_refresh(manager, deck_id, max_ids)

    manager._config_manager = manager._get_config_manager()
    pinned_conf = manager._config_manager.config
    try:
        from ..imports import sync_theme_manager_and_notify
        from ....chart_utils.theme import theme_already_synced

        if not theme_already_synced(pinned_conf):
            sync_theme_manager_and_notify(pinned_conf, source="pinned_rebuild")
    except Exception:
        log_swallowed()

    current_state = build_current_state(manager, deck_id, max_ids, pinned_conf)
    web = mw.deckBrowser.web if manager._is_deck_browser else mw.overview.web

    old_state = getattr(manager, "_last_state", None)
    if manager._overlay and manager._overlay.parent() == web and old_state == current_state:
        if not manager._overlay.isVisible():
            if getattr(manager, "_review_return_fast_path", False) and not getattr(manager, "_review_return_phase_b_active", False):
                return
            QTimer.singleShot(0, lambda: show_overlay(manager, 320))
        return

    manager._last_state = current_state
    manager._last_geom = None

    should_full_rebuild = ensure_overlay_and_rebuild_mode(
        manager,
        web=web,
        pinned_conf=pinned_conf,
        deck_id=deck_id,
    )

    history_cache = manager.__class__._global_history_cache
    global_cache = manager.__class__._global_cache_instance

    if defer_if_global_cache_uninitialized(manager, deck_id, global_cache):
        return

    pinned_defs, normalized_defs = collect_pinned_defs(manager, deck_id)
    if handle_empty_pinned_defs(manager, pinned_defs):
        return
    remove_stale_widgets(manager, pinned_defs)
    prewarm_deck_data(manager, deck_id, pinned_defs)

    if should_full_rebuild:
        reset_layout_for_full_rebuild(manager)

    stat_defs = [d for d in pinned_defs if d.get("type") == "stat_card"]
    other_defs = [d for d in pinned_defs if d.get("type") != "stat_card"]
    other_defs, should_animate_chart_reflow = prepare_other_defs_and_reflow(
        manager,
        other_defs=other_defs,
        pinned_conf=pinned_conf,
        review_return_light_mode=review_return_light_mode,
        should_full_rebuild=should_full_rebuild,
        deck_id=deck_id,
    )

    has_widgets = False
    has_widgets = has_widgets or rebuild_stat_cards(
        manager,
        stat_defs=stat_defs,
        normalized_defs=normalized_defs,
        deck_id=deck_id,
        max_ids=max_ids,
        history_cache=history_cache,
        non_blocking_update=non_blocking_update,
        review_return_phase_b_mode=review_return_phase_b_mode,
        review_return_light_mode=review_return_light_mode,
        overview_light_mode=overview_light_mode,
        pinned_conf=pinned_conf,
    )

    if other_defs:
        charts_exist, widget_index, overview_sync_budget = prepare_charts_layout(
            manager,
            other_defs=other_defs,
            pinned_conf=pinned_conf,
            should_full_rebuild=should_full_rebuild,
            should_animate_chart_reflow=should_animate_chart_reflow,
            overview_light_mode=overview_light_mode,
            review_return_light_mode=review_return_light_mode,
            review_return_phase_b_mode=review_return_phase_b_mode,
            non_blocking_update=non_blocking_update,
            deck_id=deck_id,
        )

        has_widgets, charts_exist, widget_index = rebuild_charts_widgets(
            manager,
            other_defs=other_defs,
            normalized_defs=normalized_defs,
            deck_id=deck_id,
            max_ids=max_ids,
            history_cache=history_cache,
            non_blocking_update=non_blocking_update,
            review_return_light_mode=review_return_light_mode,
            review_return_phase_b_mode=review_return_phase_b_mode,
            overview_light_mode=overview_light_mode,
            overview_sync_budget=overview_sync_budget,
            pinned_conf=pinned_conf,
            charts_exist=charts_exist,
            widget_index=widget_index,
            has_widgets=has_widgets,
            should_full_rebuild=should_full_rebuild,
        )

    apply_block_layout_order(
        manager,
        pinned_conf=pinned_conf,
        add_stretch=bool(has_widgets and should_full_rebuild),
    )

    # Rebuilt cards are created unscaled: force the next sync to reapply the webview zoom.
    manager._last_zoom = None

    finalize_rebuild(
        manager,
        has_widgets=has_widgets,
        overview_light_mode=overview_light_mode,
        review_return_light_mode=review_return_light_mode,
        review_return_phase_b_mode=review_return_phase_b_mode,
        should_full_rebuild=should_full_rebuild,
        deck_id=deck_id,
    )



