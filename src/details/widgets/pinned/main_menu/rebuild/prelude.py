# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from aqt import mw
from aqt.qt import QTimer

from ..imports import Config, Period
from ...store.registry import WidgetRegistry
from .....logic.logger import log_swallowed


def compute_rebuild_modes(manager, deck_id):
    try:
        manager._layout_gap_logged = False
    except Exception:
        log_swallowed()
    non_blocking_update = bool(getattr(manager, "_force_non_blocking_rebuild", False))
    overview_light_mode = bool(mw.state == "overview")
    review_return_light_mode = bool(
        mw.state == "deckBrowser" and getattr(manager, "_review_return_fast_path", False)
    )
    review_return_phase_b_mode = bool(review_return_light_mode and non_blocking_update)
    if overview_light_mode and not getattr(manager, "_review_return_fast_path", False):
        non_blocking_update = True
    manager._force_non_blocking_rebuild = False
    return non_blocking_update, overview_light_mode, review_return_light_mode, review_return_phase_b_mode


def strip_main_layout_spacers(manager):
    # Remove stale spacer/stretch items that can create large visual gaps.
    if getattr(manager, "_main_layout", None) is None:
        return
    try:
        while True:
            removed_any = False
            for i in range(manager._main_layout.count()):
                it = manager._main_layout.itemAt(i)
                if it is None:
                    continue
                try:
                    if it.spacerItem() is not None:
                        manager._main_layout.takeAt(i)
                        removed_any = True
                        break
                except Exception:
                    continue
            if not removed_any:
                break
    except Exception:
        log_swallowed()


def resolve_max_ids(manager, deck_id):
    # During review-return phase A skip the DB query: the background delta worker holds the SQLite
    # lock and would block the main thread. _widget_update_signatures is empty, so all widgets
    # update anyway; phase B (non_blocking=True) re-runs with fresh ids.
    if getattr(manager, "_review_return_fast_path", False):
        last = getattr(manager.__class__, "_last_max_ids", None)
        if last is not None:
            return last
    try:
        if not mw.col or not mw.col.db:
            return None
        from ...widget_factory.utils import _get_max_ids

        max_ids = _get_max_ids()
    except Exception:
        max_ids = (0, 0)
    return max_ids


def run_incremental_cache_refresh(manager, deck_id, max_ids):
    max_ids_changed = getattr(manager.__class__, "_last_max_ids", None) != max_ids
    prev_max_ids = getattr(manager.__class__, "_last_max_ids", None)
    if prev_max_ids is None and max_ids_changed:
        manager.__class__._last_max_ids = max_ids
    elif max_ids_changed and getattr(manager, "_skip_next_silent_refresh", False):
        manager.__class__._last_max_ids = max_ids
        manager._skip_next_silent_refresh = False
    elif (
        max_ids_changed
        and not getattr(manager, "_review_return_fast_path", False)
        and not getattr(manager, "_silent_refreshing", False)
    ):
        from ..imports import GlobalHistoryCache

        manager.__class__._last_max_ids = max_ids

        def _silent_update():
            from ...widget_factory.utils import PinnedDataManager, _get_max_ids
            from ..imports import GlobalHistoryCache

            cm = manager._get_config_manager()
            did = manager._current_deck_id

            def _bg_prewarm():
                max_ids_local = _get_max_ids()
                targets = {
                    (None, int(Period.TOTAL), 7, "relative", "", ""),
                    (None, int(Period.YEAR), 7, "relative", "", ""),
                    (None, int(Period.LAST_YEAR), 7, "relative", "", ""),
                }
                if did is not None:
                    targets.add((did, int(Period.TOTAL), 7, "relative", "", ""))
                    targets.add((did, int(Period.YEAR), 7, "relative", "", ""))
                    targets.add((did, int(Period.LAST_YEAR), 7, "relative", "", ""))

                for wdef in WidgetRegistry.get_all():
                    wtype = wdef.get("type", "")
                    span = manager._normalize_time_span(wdef.get("time_span"), wtype)
                    custom_days = int(wdef.get("custom_days", 7) or 7)
                    custom_type = (wdef.get("custom_type") or "relative")
                    start_date_str = (wdef.get("start_date_str") or "")
                    end_date_str = (wdef.get("end_date_str") or "")
                    targets.add((did, int(span), custom_days, custom_type, start_date_str, end_date_str))

                for t_did, t_span, t_days, t_type, t_start, t_end in targets:
                    key = (t_did, t_span, t_days, t_type, t_start, t_end, max_ids_local)
                    if key in PinnedDataManager._context_cache:
                        continue
                    ctx = GlobalHistoryCache.get_context(
                        t_did,
                        t_span,
                        cfg=cm,
                        custom_days=t_days,
                        custom_type=t_type,
                        start_date_str=t_start,
                        end_date_str=t_end,
                        allow_sync_check=False,
                    )
                    if ctx:
                        PinnedDataManager._context_cache[key] = ctx
                return len(targets)

            def _on_prewarm_done(future):
                try:
                    future.result()
                except Exception:
                    log_swallowed()
                fresh_ids = _get_max_ids()
                stale = [k for k in PinnedDataManager._context_cache if k[-1] != fresh_ids]
                for k in stale:
                    PinnedDataManager._context_cache.pop(k, None)

                def _do_refresh():
                    manager._silent_refreshing = True
                    try:
                        manager.refresh(clear_cache=False)
                    finally:
                        manager._silent_refreshing = False

                QTimer.singleShot(200, _do_refresh)

            mw.taskman.run_in_background(_bg_prewarm, on_done=_on_prewarm_done)

        warmup_targets = [None]
        current_did = manager._current_deck_id
        if current_did is not None:
            warmup_targets.append(current_did)
        elif manager._last_review_deck_id is not None:
            warmup_targets.append(manager._last_review_deck_id)

        GlobalHistoryCache().refresh_incremental(
            callback=_silent_update,
            warmup_deck_ids=warmup_targets,
        )


def build_current_state(manager, deck_id, max_ids, pinned_conf):
    config_tuple = (
        pinned_conf.get(Config.PINNED_WIDGETS, []),
        pinned_conf.get(Config.PINNED_GLASS, True),
        pinned_conf.get(Config.PINNED_GLASS_INTENSITY, 20),
        pinned_conf.get(Config.PINNED_GLASS_BLUR, 0),
        pinned_conf.get(Config.PINNED_GLASS_BORDER, 50),
        pinned_conf.get(Config.HEATMAP_SCALE, 100),
        pinned_conf.get(Config.HEATMAP_COLOR, "#3b82f6"),
        pinned_conf.get(Config.HEATMAP_SHOW_FUTURE, True),
        pinned_conf.get(Config.HEATMAP_TINTED_FUTURE, False),
        pinned_conf.get(Config.HEATMAP_ROUNDED, False),
        pinned_conf.get(Config.HEATMAP_ROUNDING, 30),
        pinned_conf.get(Config.HEATMAP_MULTI_HUE_INTENSITY, False),
        pinned_conf.get(Config.HEATMAP_MONDAY_FIRST, False),
        pinned_conf.get(Config.HEATMAP_NAV_POS, "top_right"),
        pinned_conf.get(Config.HEATMAP_EMPTY_OPACITY, 15),
        pinned_conf.get(Config.HEATMAP_FILLED_OPACITY, 100),
        pinned_conf.get(Config.HEATMAP_EMPTY_WHITE, False),
        pinned_conf.get(Config.HEATMAP_HIDE_TITLE, True),
        pinned_conf.get(Config.HEATMAP_HIDE_LABELS, False),
        pinned_conf.get(Config.HEATMAP_SHOW_LEGEND, True),
        pinned_conf.get(Config.HEATMAP_SHOW_GLASS, False),
        pinned_conf.get(Config.HEATMAP_GLASS_INTENSITY, 43),
        pinned_conf.get(Config.HEATMAP_GLASS_BLUR, 0),
        pinned_conf.get(Config.HEATMAP_GLASS_BORDER, 0),
        pinned_conf.get(Config.PINNED_BLOCK_ORDER, ["stats", "charts"]),
        pinned_conf.get(Config.FACECARDS_SCALE, 100),
        pinned_conf.get(Config.FACECARDS_TITLE_SHADOW_INTENSITY, 40),
        pinned_conf.get(Config.FACECARDS_STAT_SHADOW_INTENSITY, 60),
        pinned_conf.get(Config.FACECARDS_GLASS_BORDER, 50),
        pinned_conf.get(Config.FACECARDS_GLASS_INTENSITY, 5),
        pinned_conf.get(Config.FACECARDS_GLASS_BLUR, 0),
    )
    try:
        from ...widget_factory.utils import cache_data_version

        data_version = cache_data_version()
    except Exception:
        data_version = None
    return (deck_id, max_ids, data_version, config_tuple)


def defer_if_global_cache_uninitialized(manager, deck_id, global_cache):
    if global_cache is None or getattr(global_cache, "is_initialized", False):
        return False
    if manager._overlay:
        manager._overlay.hide()
    manager._update_placeholder_height(0)

    manager._widget_update_signatures = {}
    manager._last_state = None

    if not manager._initial_rebuild_queued:
        manager._initial_rebuild_queued = True

        def _on_cache_ready():
            manager._initial_rebuild_queued = False
            QTimer.singleShot(0, lambda: manager.refresh(clear_cache=False))

        global_cache.init_async(callback=_on_cache_ready)
    return True


