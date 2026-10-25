# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..imports import mw
from ..constants import IMMEDIATE_TIMER_MS, POLL_INTERVAL_MS
from .....logic.logger import log_swallowed


def refresh(manager, clear_cache=True):
    if manager._external_refresh_suspensions:
        manager._pending_refresh_while_suspended = True
        manager._pending_refresh_clear_cache = (
            manager._pending_refresh_clear_cache or bool(clear_cache)
        )
        return
    # Instead of forcing Anki to reload HTML/queries, coalesce our own widget refresh.
    if mw.state not in ("deckBrowser", "overview"):
        return

    if getattr(manager, "_review_return_fast_path", False):
        return

    manager._refresh_clear_cache = manager._refresh_clear_cache or clear_cache
    if not manager._refresh_timer.isActive():
        manager._refresh_timer.start(IMMEDIATE_TIMER_MS)


def set_external_refresh_suspended(manager, suspended: bool, reason: str = "external"):
    """Allow external flows (e.g., Details window open) to pause pinned rebuilds."""
    r = str(reason or "external")
    if suspended:
        manager._external_refresh_suspensions.add(r)
        try:
            if hasattr(manager, "_poll_timer") and manager._poll_timer.isActive():
                manager._poll_timer.stop()
            if hasattr(manager, "_sync_timer"):
                manager._sync_timer.stop()
            if hasattr(manager, "_settle_sync_timer"):
                manager._settle_sync_timer.stop()
        except Exception:
            log_swallowed()
        return
    if r in manager._external_refresh_suspensions:
        manager._external_refresh_suspensions.remove(r)
    try:
        if (
            not manager._external_refresh_suspensions
            and hasattr(manager, "_poll_timer")
            and not manager._poll_timer.isActive()
        ):
            manager._poll_timer.start(POLL_INTERVAL_MS)
    except Exception:
        log_swallowed()
    if not manager._external_refresh_suspensions and manager._pending_refresh_while_suspended:
        pending_clear = bool(manager._pending_refresh_clear_cache)
        manager._pending_refresh_while_suspended = False
        manager._pending_refresh_clear_cache = False
        manager.refresh(clear_cache=pending_clear)




