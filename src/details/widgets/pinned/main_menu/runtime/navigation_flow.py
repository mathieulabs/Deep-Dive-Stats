# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import time

from aqt import mw
from aqt.qt import QTimer
from .....logic.logger import log_swallowed


_REVIEW_RETURN_PHASE_B_INITIAL_DELAY_MS = 80
_REVIEW_RETURN_BROWSER_GRACE_MS = 45
_REVIEW_RETURN_BROWSER_RETRY_MS = 18
_REVIEW_RETURN_BROWSER_MAX_WAIT_MS = 420


_REVIEW_RETURN_WATCHDOG_MS = (1500, 4000)


def _end_review_return(manager, reason):
    """Leave the review-return mode and rebuild normally, so the widgets show."""
    manager._review_return_phase_b_active = False
    manager._review_return_fast_path = False
    manager._review_return_t0 = None
    manager._widget_update_signatures = {}
    manager._last_state = None
    try:
        from ...widget_factory.utils import PinnedDataManager, invalidate_max_ids_cache

        PinnedDataManager.clear()
        invalidate_max_ids_cache()
        manager.__class__._last_max_ids = None
    except Exception:
        log_swallowed()
    if mw.state in ("deckBrowser", "overview"):
        manager._schedule_rebuild(manager._current_deck_id, force=True)


def _arm_review_return_watchdog(manager, seq):
    """Guard against widgets staying hidden after a review.

    They stay hidden until phase B shows them. If phase B never completes, check
    twice and force a normal rebuild.
    """

    def _check(attempt):
        if getattr(manager, "_review_return_seq", None) != seq:
            return
        if mw.state not in ("deckBrowser", "overview"):
            return
        if manager._external_refresh_suspensions:
            return
        overlay = getattr(manager, "_overlay", None)
        try:
            visible = bool(overlay is not None and overlay.isVisible())
        except RuntimeError:
            visible = False
        has_widgets = bool(getattr(manager, "_active_widgets", None))
        stuck = bool(getattr(manager, "_review_return_phase_b_active", False) or getattr(manager, "_review_return_fast_path", False))
        if visible and not stuck:
            return
        if not visible and not has_widgets and not stuck:
            return  # nothing pinned here
        if stuck and attempt == 0:
            # Phase B may still be running on a slow collection: give it more time,
            # unless the cache is idle (then its callback was lost).
            try:
                from ..imports import GlobalHistoryCache

                if GlobalHistoryCache()._is_refreshing:
                    QTimer.singleShot(_REVIEW_RETURN_WATCHDOG_MS[1] - _REVIEW_RETURN_WATCHDOG_MS[0], lambda: _check(1))
                    return
            except Exception:
                log_swallowed()
        try:
            from ..imports import log_info

            log_info(f"Review return watchdog: widgets not shown (stuck={stuck}), forcing a rebuild.", tag="PINNED")
        except Exception:
            log_swallowed()
        _end_review_return(manager, reason="watchdog")

    QTimer.singleShot(_REVIEW_RETURN_WATCHDOG_MS[0], lambda: _check(0))


def on_state_did_change(manager, new_state, old_state):
    if new_state == "review":
        if manager._overlay:
            manager._overlay.hide()
        manager._update_placeholder_height(0)
    elif old_state == "overview" and new_state == "deckBrowser":
        manager._is_deck_browser = True
        manager._current_deck_id = None
        manager._widget_update_signatures = {}
        manager._last_state = None
        manager._pending_browser_refresh = True

        def _fallback_browser_rebuild():
            if manager._pending_browser_refresh and mw.state == "deckBrowser":
                manager._pending_browser_refresh = False
                manager._schedule_rebuild(None, force=True)

        QTimer.singleShot(180, _fallback_browser_rebuild)
    elif old_state == "review" and new_state in ("deckBrowser", "overview"):
        try:
            from ..imports import GlobalHistoryCache
            GlobalHistoryCache()._skip_next_warmup = True
        except Exception:
            log_swallowed()
        manager._review_return_seq += 1
        manager._review_return_t0 = time.perf_counter()
        manager._review_return_fast_path = True
        manager._review_return_phase_b_active = False
        manager._last_review_return_rebuild_sig = None
        manager._last_review_return_rebuild_ts = 0.0
        manager._review_return_browser_seen = False
        manager._review_return_browser_rendered_at = 0.0
        if new_state == "deckBrowser":
            manager._is_deck_browser = True
            manager._current_deck_id = None
        else:
            manager._is_deck_browser = False
            try:
                manager._current_deck_id = mw.col.decks.selected()
            except Exception:
                manager._current_deck_id = None

        manager._schedule_rebuild(manager._current_deck_id, force=True)

        def _deferred_prewarm():
            browser_seen = bool(getattr(manager, "_review_return_browser_seen", False))
            browser_rendered_at = float(getattr(manager, "_review_return_browser_rendered_at", 0.0) or 0.0)
            if new_state == "deckBrowser":
                if not browser_seen:
                    elapsed_ms = manager._review_elapsed_ms()
                    if elapsed_ms is not None and elapsed_ms < _REVIEW_RETURN_BROWSER_MAX_WAIT_MS:
                        QTimer.singleShot(_REVIEW_RETURN_BROWSER_RETRY_MS, _deferred_prewarm)
                        return
                elif browser_rendered_at > 0.0:
                    since_browser_ms = (time.perf_counter() - browser_rendered_at) * 1000
                    if since_browser_ms < _REVIEW_RETURN_BROWSER_GRACE_MS:
                        retry_ms = max(
                            _REVIEW_RETURN_BROWSER_RETRY_MS,
                            int(_REVIEW_RETURN_BROWSER_GRACE_MS - since_browser_ms),
                        )
                        QTimer.singleShot(retry_ms, _deferred_prewarm)
                        return
            if not getattr(manager, "_silent_refreshing", False):
                try:
                    from ..imports import GlobalHistoryCache

                    manager._review_return_phase_b_active = True
                    if manager._rebuild_timer and manager._rebuild_timer.isActive():
                        manager._rebuild_timer.stop()

                    def _after_incremental():
                        manager._review_return_phase_b_active = False
                        try:
                            from ....charts.heatmap import HeatmapWidget

                            for widget in list(getattr(manager, "_active_widgets", {}).values()):
                                if widget is None:
                                    continue
                                chart = widget if isinstance(widget, HeatmapWidget) else widget.findChild(HeatmapWidget)
                                if chart is None:
                                    continue
                                chart._force_runtime_refresh_once = True
                                chart._last_runtime_refresh_key = None
                                chart._last_applied_runtime_refresh_key = None
                        except Exception:
                            log_swallowed()
                        try:
                            from ...widget_factory.utils import (
                                PinnedDataManager,
                                invalidate_max_ids_cache,
                                refresh_max_ids_cache_now,
                                _last_max_ids_cache,
                            )

                            PinnedDataManager.clear()
                            # Use the max IDs already known to GlobalHistoryCache (set by the
                            # phase-B worker) instead of two fresh DB queries, and update the class-
                            # level fast-path cache so resolve_max_ids returns fresh values and
                            # widget signatures diverge without a full clear.
                            try:
                                ghc = GlobalHistoryCache()
                                fresh_rev = ghc.last_max_rev_id or 0
                                fresh_card = ghc.last_max_card_id or 0
                                if fresh_rev > 0:
                                    _last_max_ids_cache["rev_id"] = fresh_rev
                                    _last_max_ids_cache["card_id"] = fresh_card
                                    _last_max_ids_cache["time"] = time.time()
                                    manager.__class__._last_max_ids = (fresh_rev, fresh_card)
                                else:
                                    invalidate_max_ids_cache()
                                    refresh_max_ids_cache_now()
                            except Exception:
                                invalidate_max_ids_cache()
                                refresh_max_ids_cache_now()
                        except Exception:
                            log_swallowed()
                        manager._widget_update_signatures = {}
                        manager._last_state = None
                        manager._force_non_blocking_rebuild = True
                        manager._skip_next_silent_refresh = True
                        target_deck_id = manager._current_deck_id
                        manager._schedule_rebuild(target_deck_id, force=True)
                        manager._review_return_t0 = None
                        QTimer.singleShot(120, lambda: setattr(manager, "_review_return_fast_path", False))
                        # Warm the reviewed deck's overview ranges in background so the
                        # next overview navigation finds hot data (prevents prefetch miss).
                        try:
                            _warmup_did = getattr(manager, "_last_review_deck_id", None)
                            if _warmup_did is not None:
                                from ......config import ConfigManager as _CM
                                def _warm_overview_deck(_did=_warmup_did):
                                    try:
                                        GlobalHistoryCache().warmup_selected_decks(
                                            [_did, None], cfg=_CM(mw)
                                        )
                                    except Exception:
                                        log_swallowed()
                                mw.taskman.run_in_background(_warm_overview_deck)
                        except Exception:
                            log_swallowed()

                    warmup_targets = [None]
                    if manager._current_deck_id is not None:
                        warmup_targets.append(manager._current_deck_id)
                    elif manager._last_review_deck_id is not None:
                        warmup_targets.append(manager._last_review_deck_id)
                    optimistic_rev_max = max(
                        int(time.time() * 1000),
                        int(getattr(GlobalHistoryCache(), "last_max_rev_id", 0) or 0),
                    )
                    GlobalHistoryCache().refresh_incremental(
                        callback=_after_incremental,
                        warmup_deck_ids=warmup_targets,
                        skip_warmup=True,
                        max_rev_hint=optimistic_rev_max,
                    )
                except Exception:
                    _end_review_return(manager, reason="phase_b_dispatch_error")

        QTimer.singleShot(_REVIEW_RETURN_PHASE_B_INITIAL_DELAY_MS, _deferred_prewarm)
        _arm_review_return_watchdog(manager, manager._review_return_seq)


def on_deck_browser_will_render(manager, _browser, content):
    t0 = time.perf_counter()
    if getattr(manager, "_review_return_fast_path", False) and not getattr(manager, "_review_return_browser_seen", False):
        manager._review_return_browser_seen = True
        manager._review_return_browser_rendered_at = t0

    manager._is_deck_browser = True
    manager._current_deck_id = None
    pending_browser_refresh = bool(getattr(manager, "_pending_browser_refresh", False))
    now_ts = time.time()
    duplicate_browser_burst = (now_ts - float(getattr(manager, "_last_browser_rebuild_ts", 0.0) or 0.0)) < 0.25
    if pending_browser_refresh:
        duplicate_browser_burst = False

    if not duplicate_browser_burst:
        from ...context_access import get_pinned_contexts
        from ...widget_factory.utils import Period

        cm = manager._get_config_manager()
        get_pinned_contexts(None, (Period.TOTAL, Period.YEAR, Period.LAST_YEAR), cfg=cm, allow_slow_ops=False)

    manager._inject_placeholder(content, is_browser=True)

    if not duplicate_browser_burst:
        manager._schedule_rebuild(None, force=pending_browser_refresh, after_page_load=True)
        manager._last_browser_rebuild_ts = now_ts
        manager._pending_browser_refresh = False


def on_overview_will_render(manager, overview, content):
    manager._is_deck_browser = False
    try:
        did = overview.mw.col.decks.selected()
    except Exception:
        did = None
    manager._current_deck_id = did
    now_ts = time.time()
    last_did, last_ts = getattr(manager, "_last_overview_rebuild_sig", (None, 0.0))
    duplicate_overview_burst = did == last_did and (now_ts - float(last_ts or 0.0)) < 0.25

    if did is not None and not duplicate_overview_burst:
        # Pulls the deck's contexts from the history cache now, so the widgets built
        # next find them ready.
        from ...context_access import get_pinned_contexts
        from ...widget_factory.utils import Period

        cm = manager._get_config_manager()
        get_pinned_contexts(did, (Period.TOTAL, Period.YEAR, Period.LAST_YEAR), cfg=cm, allow_slow_ops=False)

    manager._inject_placeholder(content, is_browser=False)
    if not duplicate_overview_burst:
        manager._schedule_rebuild(did, after_page_load=True)
        manager._last_overview_rebuild_sig = (did, now_ts)


def on_reviewer_did_init(manager, _reviewer):
    try:
        manager._last_review_deck_id = mw.col.decks.selected()
    except Exception:
        manager._last_review_deck_id = None
    if manager._overlay:
        manager._overlay.hide()
        manager._update_placeholder_height(0)


def on_reviewer_will_end(manager):
    if manager._overlay:
        manager._overlay.hide()



