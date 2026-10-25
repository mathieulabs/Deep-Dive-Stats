# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import time

from ..imports import QTimer, mw
from ..constants import IMMEDIATE_TIMER_MS
from .....logic.logger import log_swallowed


def on_rebuild_timer_timeout(manager):
    if manager._external_refresh_suspensions:
        return
    if getattr(manager, "_review_return_phase_b_active", False):
        return
    # The duplicate guard is for phase-A bursts only. The phase-B rebuild (flagged
    # by _force_non_blocking_rebuild) shows the widgets again, and when the delta
    # refresh was fast it landed within 60 ms of phase A and was dropped, leaving
    # the widgets hidden.
    if getattr(manager, "_review_return_fast_path", False) and not getattr(manager, "_force_non_blocking_rebuild", False):
        current_sig = (manager._scheduled_deck_id, mw.state)
        last_sig = getattr(manager, "_last_review_return_rebuild_sig", None)
        last_ts = float(getattr(manager, "_last_review_return_rebuild_ts", 0.0) or 0.0)
        if last_sig == current_sig and last_ts:
            elapsed_ms = (time.perf_counter() - last_ts) * 1000.0
            if elapsed_ms < 60.0:
                return
    manager._rebuild_overlay(manager._scheduled_deck_id)


def on_refresh_timer_timeout(manager):
    if manager._external_refresh_suspensions:
        manager._pending_refresh_while_suspended = True
        manager._pending_refresh_clear_cache = (
            manager._pending_refresh_clear_cache or bool(manager._refresh_clear_cache)
        )
        manager._refresh_clear_cache = False
        return
    if mw.state not in ("deckBrowser", "overview"):
        manager._refresh_clear_cache = False
        return

    manager._last_state = None
    if manager._refresh_clear_cache:
        from ...widget_factory.utils import PinnedDataManager

        PinnedDataManager.clear()
    manager._refresh_clear_cache = False
    manager._schedule_rebuild(manager._current_deck_id)


_PAGE_LOAD_MAX_WAIT_MS = 350


def _start_rebuild_after_page_load(manager):
    """Start the rebuild once the deck list or overview page has loaded.

    Running it immediately kept the main thread busy during page load and delayed
    the deck list by about 150 ms. The page always loads right after the
    will-render hook, so wait for it, with a safety timeout.
    """
    web = None
    try:
        web = mw.deckBrowser.web if mw.state == "deckBrowser" else mw.overview.web
        page = web.page()
    except Exception:
        return False
    if getattr(manager, "_rebuild_after_load_pending", False):
        return True
    manager._rebuild_after_load_pending = True
    token = {"done": False}

    def _go(*_args):
        if token["done"]:
            return
        token["done"] = True
        manager._rebuild_after_load_pending = False
        try:
            page.loadFinished.disconnect(_go)
        except Exception:
            log_swallowed()
        if manager._rebuild_timer:
            manager._rebuild_timer.start(IMMEDIATE_TIMER_MS)

    try:
        page.loadFinished.connect(_go)
    except Exception:
        manager._rebuild_after_load_pending = False
        return False
    QTimer.singleShot(_PAGE_LOAD_MAX_WAIT_MS, _go)
    return True


def schedule_rebuild(manager, deck_id=None, force=False, after_page_load=False):
    if manager._external_refresh_suspensions:
        return
    if getattr(manager, "_review_return_phase_b_active", False):
        return
    if (
        not force
        and manager._rebuild_timer
        and manager._rebuild_timer.isActive()
        and manager._scheduled_deck_id == deck_id
    ):
        return
    manager._scheduled_deck_id = deck_id
    if (
        after_page_load
        and mw.state in ("deckBrowser", "overview")
        and not getattr(manager, "_review_return_fast_path", False)
        and _start_rebuild_after_page_load(manager)
    ):
        return
    if manager._rebuild_timer:
        # 0ms keeps deck navigation perceived as instant.
        manager._rebuild_timer.start(IMMEDIATE_TIMER_MS)


def rebuild_overlay(manager, deck_id):
    import time as _time
    manager._rebuild_in_progress = True
    try:
        manager._rebuild_overlay_inner(deck_id)
    finally:
        manager._rebuild_in_progress = False
        manager._pending_updates.clear()
        if getattr(manager, "_review_return_fast_path", False):
            manager._last_review_return_rebuild_sig = (deck_id, mw.state)
            manager._last_review_return_rebuild_ts = _time.perf_counter()




