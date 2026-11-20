# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Anki's hooks the pinned widgets follow: a sync, an edit (card, note, deck), a profile opened, the theme."""
from aqt import mw, gui_hooks
from aqt.qt import QTimer

from .....logic.logger import log_info, log_swallowed


def register_hooks(manager):
    if hasattr(gui_hooks, "reviewer_did_init"):
        gui_hooks.reviewer_did_init.append(manager._on_reviewer_did_init)
    elif hasattr(gui_hooks, "reviewer_will_init"):
        gui_hooks.reviewer_will_init.append(manager._on_reviewer_did_init)
    if hasattr(gui_hooks, "theme_did_change"):
        gui_hooks.theme_did_change.append(manager._on_theme_change)
    if hasattr(gui_hooks, "state_did_change"):
        gui_hooks.state_did_change.append(manager._on_state_did_change)
    if hasattr(gui_hooks, "sync_did_finish"):
        gui_hooks.sync_did_finish.append(manager._on_sync_did_finish)
    if hasattr(gui_hooks, "operation_did_execute"):
        gui_hooks.operation_did_execute.append(manager._on_operation_did_execute)
    gui_hooks.profile_did_open.append(manager._on_profile_did_open)

    try:
        from ..imports import sync_theme_manager_and_notify

        sync_theme_manager_and_notify(manager._get_config_manager().config, source="pinned_register")
    except Exception:
        log_swallowed()

    # Installed or turned on while Anki runs: the deck list is already on screen, drawn
    # without the room the pinned widgets go in, so it is drawn again.
    if getattr(mw, "col", None) is not None and mw.state in ("deckBrowser", "overview"):
        QTimer.singleShot(0, _redraw_page)


def _redraw_page():
    try:
        if getattr(mw, "col", None) is None:
            return
        if mw.state == "deckBrowser":
            mw.deckBrowser.refresh()
        elif mw.state == "overview":
            mw.overview.refresh()
        else:
            return
        log_info(f"Loaded with the {mw.state} page already shown: page drawn again.", tag="PINNED")
    except Exception:
        log_swallowed()


def on_sync_did_finish(manager):
    if mw.state not in ("deckBrowser", "overview"):
        return
    if manager._is_deck_browser or manager._current_deck_id is not None:
        manager.refresh()


def on_operation_did_execute(manager, changes, handler):
    try:
        handler_name = type(handler).__name__ if handler is not None else None
        deck_changed = bool(getattr(changes, "deck", False))
        deck_config_changed = bool(getattr(changes, "deck_config", False))
        if (deck_changed or deck_config_changed) and mw.state != "review":
            try:
                from ..imports import GlobalHistoryCache

                GlobalHistoryCache()._invalidate_hierarchy_context(
                    reason="deck_change" if deck_changed else "deck_config_change"
                )
            except Exception:
                log_swallowed()
        if mw.state == "review":
            return
        if (
            handler_name == "Reviewer"
            and manager._review_return_t0 is not None
            and mw.state in ("overview", "deckBrowser")
        ):
            return
        if not bool(deck_changed or deck_config_changed
                    or getattr(changes, "card", False) or getattr(changes, "note", False)):
            return
        manager._op_force_refresh = True
        manager._op_refresh_timer.start(180)
    except Exception:
        log_swallowed()


def run_operation_refresh(manager):
    """An edit: the history cache reads what changed (only the card states when nothing else did), then the pinned
    data is dropped so what is read next is fresh."""
    if not manager._op_force_refresh:
        return
    manager._op_force_refresh = False
    force_full = True
    states_only = False
    try:
        from ...widget_factory.utils import PinnedDataManager, invalidate_max_ids_cache, _get_max_ids
        from ..imports import GlobalHistoryCache
        from .....logic.history_cache.ops.refresh_monitoring import capture_db_fingerprint

        ghc = GlobalHistoryCache()
        current_max = _get_max_ids(allow_db=True)
        last_max = (int(getattr(ghc, "last_max_rev_id", 0) or 0), int(getattr(ghc, "last_max_card_id", 0) or 0))
        max_ids_decreased = current_max[0] < last_max[0] or current_max[1] < last_max[1]
        max_ids_increased = current_max[0] > last_max[0] or current_max[1] > last_max[1]
        fingerprint_prev = getattr(ghc, "_last_db_fingerprint", None)

        if max_ids_decreased:
            force_full = True
        elif max_ids_increased:
            force_full = False
        else:
            fingerprint_curr = capture_db_fingerprint(ghc)
            if fingerprint_prev is None:
                ghc._last_db_fingerprint = fingerprint_curr
                force_full = False
            else:
                fingerprint_changed = fingerprint_curr is not None and fingerprint_curr != fingerprint_prev
                if fingerprint_changed:
                    ghc._last_db_fingerprint = fingerprint_curr
                    # Same reviews, same cards in the same decks: only card states changed.
                    states_only = (
                        fingerprint_curr[:5] == fingerprint_prev[:5]
                        and fingerprint_curr[5][0] == fingerprint_prev[5][0]
                    )
                force_full = bool(fingerprint_changed) and not states_only
        PinnedDataManager.clear()
        invalidate_max_ids_cache()
    except Exception:
        log_swallowed()
    try:
        from ..imports import GlobalHistoryCache

        ghc = GlobalHistoryCache()
        # a callback, even one doing nothing: refresh_incremental skips the refreshes without one while reviewing
        if states_only:
            ghc.refresh_card_states(callback=_noop)
        else:
            ghc.refresh_incremental(callback=_noop, force_full=force_full)
    except Exception:
        log_swallowed()


def _noop():
    pass


def on_profile_did_open(manager):
    manager._mark_config_dirty()
    manager.__class__._last_max_ids = None
    try:
        # Ids belong to the previous profile.
        from ...widget_factory import utils as _wf_utils

        _wf_utils._last_max_ids_cache.update({"rev_id": 0, "card_id": 0, "time": 0})
        _wf_utils.PinnedDataManager.clear()
    except Exception:
        log_swallowed()
    try:
        from ..imports import sync_theme_manager_and_notify

        sync_theme_manager_and_notify(manager._get_config_manager().config, source="pinned_profile_open")
    except Exception:
        log_swallowed()


def on_theme_change(manager):
    from ..imports import sync_theme_manager_from_config

    sync_theme_manager_from_config(manager._get_config_manager().config, emit=True, source="anki_theme_change")
