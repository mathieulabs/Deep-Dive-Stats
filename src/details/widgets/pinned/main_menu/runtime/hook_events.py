# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt import mw, gui_hooks
from aqt.qt import QTimer, QCheckBox, QRadioButton, QWidget, QDialog

from ..imports import sync_theme_manager_from_config, sync_theme_manager_and_notify
from .....logic.logger import log_swallowed


def register_hooks(manager):
    gui_hooks.deck_browser_will_render_content.append(manager._on_deck_browser_will_render)
    gui_hooks.overview_will_render_content.append(manager._on_overview_will_render)

    if hasattr(gui_hooks, "reviewer_did_init"):
        gui_hooks.reviewer_did_init.append(manager._on_reviewer_did_init)
    elif hasattr(gui_hooks, "reviewer_will_init"):
        gui_hooks.reviewer_will_init.append(manager._on_reviewer_did_init)

    if hasattr(gui_hooks, "reviewer_will_end"):
        gui_hooks.reviewer_will_end.append(manager._on_reviewer_will_end)
    elif hasattr(gui_hooks, "reviewer_did_end"):
        gui_hooks.reviewer_did_end.append(manager._on_reviewer_will_end)

    gui_hooks.webview_did_receive_js_message.append(manager._on_js_message)
    gui_hooks.webview_did_inject_style_into_page.append(manager._on_webview_did_inject_style)

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
        cm = manager._get_config_manager()
        sync_theme_manager_and_notify(cm.config, source="pinned_register")
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
            and getattr(manager, "_review_return_t0", None) is not None
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
        fingerprint_curr = None
        fingerprint_changed = False

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

        def _after_op_refresh():
            try:
                manager._last_state = None
                manager._widget_update_signatures = {}
                manager._last_op_callback_rebuild_ts = __import__("time").perf_counter()
                manager._schedule_rebuild(manager._current_deck_id, force=True)
            except Exception:
                log_swallowed()

        if states_only:
            ghc.refresh_card_states(callback=_after_op_refresh)
        else:
            ghc.refresh_incremental(
                callback=_after_op_refresh,
                force_full=force_full,
            )

        def _maybe_safety_rebuild():
            elapsed_ms = round((__import__("time").perf_counter() - float(getattr(manager, "_last_op_callback_rebuild_ts", 0.0) or 0.0)) * 1000, 1)
            if 0.0 <= elapsed_ms < 1200.0:
                return
            manager._schedule_rebuild(manager._current_deck_id, force=True)

        QTimer.singleShot(900, _maybe_safety_rebuild)
    except Exception:
        log_swallowed()


def on_profile_did_open(manager):
    manager._mark_config_dirty()
    manager._last_state = None
    manager._last_widget_set = None
    manager.__class__._last_max_ids = None

    try:
        # Ids and browsed heatmap years belong to the previous profile.
        from ...widget_factory import utils as _wf_utils
        from ...widget_factory.builders import heatmap as _wf_heatmap
        _wf_utils._last_max_ids_cache.update({"rev_id": 0, "card_id": 0, "time": 0})
        _wf_heatmap._SESSION_YEARS.clear()
    except Exception:
        log_swallowed()

    try:
        from ...widget_factory.utils import PinnedDataManager
        PinnedDataManager.clear()
    except Exception:
        log_swallowed()

    cm = manager._get_config_manager()
    sync_theme_manager_and_notify(cm.config, source="pinned_profile_open")
    if mw.state in ("deckBrowser", "overview"):
        manager._last_state = None
        QTimer.singleShot(0, lambda: manager.refresh(clear_cache=False))


def on_internal_theme_changed(manager, _source=None):
    if manager._overlay and manager._overlay.isVisible():
        manager.update_styles()
        from ...widget_factory.utils import _apply_checkbox_style, _apply_radio_style
        for cb in (w for w in manager._overlay.findChildren(QCheckBox) if not isinstance(w.window(), QDialog)):
            try:
                _apply_checkbox_style(cb)
            except Exception:
                log_swallowed()
        for rb in (w for w in manager._overlay.findChildren(QRadioButton) if not isinstance(w.window(), QDialog)):
            try:
                _apply_radio_style(rb)
            except Exception:
                log_swallowed()
        for widget in manager._overlay.findChildren(QWidget):
            try:
                widget.update()
            except Exception:
                continue


def on_theme_change(manager):
    cm = manager._get_config_manager()
    sync_theme_manager_from_config(cm.config, emit=True, source="anki_theme_change")





