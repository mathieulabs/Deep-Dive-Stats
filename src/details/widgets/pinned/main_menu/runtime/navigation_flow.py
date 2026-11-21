# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The return to the deck list or a deck's screen after reviewing.

The page is drawn at once with the pinned data from before (phase A). A moment later the history cache reads the new
reviews (phase B) and the pinned data is dropped, so what is read next is fresh. Phase B waits for the page: started
with it, its reading held Anki's UI thread while the page was drawn."""
import time

from aqt import mw
from aqt.qt import QTimer
from .....logic.logger import log_swallowed

# After the deck screen; after the deck list, which is longer to draw (as long as the native overlay waited for it)
_PHASE_B_DELAY_MS = 80
_PHASE_B_DELAY_BROWSER_MS = 420
# Phase B not done after these times (its callback lost): the review return ends anyway
_WATCHDOG_MS = (1500, 4000)


def _clear_pinned_data():
    from ...widget_factory.utils import PinnedDataManager

    PinnedDataManager.clear()


def _end_review_return(manager):
    """Leave the review-return mode: the pinned data is read again from the database."""
    manager._review_return_phase_b_active = False
    manager._review_return_fast_path = False
    manager._review_return_t0 = None
    try:
        from ...widget_factory.utils import invalidate_max_ids_cache

        _clear_pinned_data()
        invalidate_max_ids_cache()
    except Exception:
        log_swallowed()


def _arm_watchdog(manager, seq):
    def _check(attempt):
        if manager._review_return_seq != seq or mw.state not in ("deckBrowser", "overview"):
            return
        if not (manager._review_return_phase_b_active or manager._review_return_fast_path):
            return
        if attempt == 0:
            # Phase B may still run on a slow collection: more time, unless the cache is idle (its callback lost)
            try:
                from .....logic.history_cache import GlobalHistoryCache

                if GlobalHistoryCache()._is_refreshing:
                    QTimer.singleShot(_WATCHDOG_MS[1] - _WATCHDOG_MS[0], lambda: _check(1))
                    return
            except Exception:
                log_swallowed()
        try:
            from .....logic import log_info

            log_info("Review return watchdog: phase B not done, the pinned data read again.", tag="PINNED")
        except Exception:
            log_swallowed()
        _end_review_return(manager)

    QTimer.singleShot(_WATCHDOG_MS[0], lambda: _check(0))


def _phase_b(manager, seq):
    if manager._review_return_seq != seq:
        return
    try:
        from .....logic.history_cache import GlobalHistoryCache

        manager._review_return_phase_b_active = True

        def _after_incremental():
            manager._review_return_phase_b_active = False
            try:
                from ...widget_factory.utils import (
                    invalidate_max_ids_cache,
                    refresh_max_ids_cache_now,
                    _last_max_ids_cache,
                )

                _clear_pinned_data()
                # The max ids the phase-B worker already read, not two more queries
                try:
                    ghc = GlobalHistoryCache()
                    fresh_rev = ghc.last_max_rev_id or 0
                    fresh_card = ghc.last_max_card_id or 0
                    if fresh_rev > 0:
                        _last_max_ids_cache["rev_id"] = fresh_rev
                        _last_max_ids_cache["card_id"] = fresh_card
                        _last_max_ids_cache["time"] = time.time()
                    else:
                        invalidate_max_ids_cache()
                        refresh_max_ids_cache_now()
                except Exception:
                    invalidate_max_ids_cache()
                    refresh_max_ids_cache_now()
            except Exception:
                log_swallowed()
            manager._review_return_t0 = None
            QTimer.singleShot(120, lambda: setattr(manager, "_review_return_fast_path", False))
            # The reviewed deck's ranges warmed in the background: its screen, opened next, finds them ready
            did = manager._last_review_deck_id
            if did is not None:
                from ......config import ConfigManager

                def _warm(_did=did):
                    try:
                        GlobalHistoryCache().warmup_selected_decks([_did, None], cfg=ConfigManager(mw))
                    except Exception:
                        log_swallowed()

                mw.taskman.run_in_background(_warm)

        targets = [None]
        if manager._current_deck_id is not None:
            targets.append(manager._current_deck_id)
        elif manager._last_review_deck_id is not None:
            targets.append(manager._last_review_deck_id)
        GlobalHistoryCache().refresh_incremental(
            callback=_after_incremental,
            warmup_deck_ids=targets,
            skip_warmup=True,
            max_rev_hint=max(int(time.time() * 1000), int(GlobalHistoryCache().last_max_rev_id or 0)),
        )
    except Exception:
        _end_review_return(manager)


def on_state_did_change(manager, new_state, old_state):
    if old_state == "overview" and new_state == "deckBrowser":
        manager._is_deck_browser = True
        manager._current_deck_id = None
    elif old_state == "review" and new_state in ("deckBrowser", "overview"):
        try:
            from .....logic.history_cache import GlobalHistoryCache

            GlobalHistoryCache()._skip_next_warmup = True
        except Exception:
            log_swallowed()
        manager._review_return_seq += 1
        seq = manager._review_return_seq
        manager._review_return_t0 = time.perf_counter()
        manager._review_return_fast_path = True
        manager._review_return_phase_b_active = False
        if new_state == "deckBrowser":
            manager._is_deck_browser = True
            manager._current_deck_id = None
        else:
            manager._is_deck_browser = False
            try:
                manager._current_deck_id = mw.col.decks.selected()
            except Exception:
                manager._current_deck_id = None
        delay = _PHASE_B_DELAY_BROWSER_MS if new_state == "deckBrowser" else _PHASE_B_DELAY_MS
        QTimer.singleShot(delay, lambda: _phase_b(manager, seq))
        _arm_watchdog(manager, seq)


def on_reviewer_did_init(manager, _reviewer):
    try:
        manager._last_review_deck_id = mw.col.decks.selected()
    except Exception:
        manager._last_review_deck_id = None
