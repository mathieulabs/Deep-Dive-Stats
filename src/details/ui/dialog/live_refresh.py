# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Keep an open Deep Dive window up to date when the collection changes.

Once the history cache has merged a change, the window reloads its tables and
panel in place (same view, tab, deck and period).

When it reloads:
- immediately, if the window is open but not focused;
- on mouse release, if it is focused (never during a zoom, drag or click);
- on F5, at any time.
"""

from aqt import mw
from aqt.qt import QApplication, QKeySequence, QShortcut, Qt, QTimer
from ...logic.logger import log_swallowed


_DEBOUNCE_MS = 350
_BUSY_RETRY_MS = 400


def _data_signature():
    try:
        from ...logic.history_cache import GlobalHistoryCache

        ghc = GlobalHistoryCache()
        if not ghc.is_initialized or not ghc.last_max_rev_id:
            return None  # cache still loading: the window's own load handles it
        try:
            from ...logic.history_cache.population import snapshot_version

            snap = snapshot_version()
        except Exception:
            snap = None
        # The snapshot pass (card counts, future due, intervals, hourly) lands just
        # after the merge without new ids; the debounce folds both into one reload.
        try:
            from datetime import datetime, timedelta
            from ....utils import rollover_hour

            day = (datetime.now() - timedelta(hours=rollover_hour())).date().toordinal()
        except Exception:
            day = None
        return (
            int(getattr(mw.col, "mod", 0) or 0),
            int(ghc.last_max_rev_id or 0),
            int(ghc.last_max_card_id or 0),
            snap,
            day,  # day rollover: the cache rebuilds without new ids
        )
    except Exception:
        return None


def _alive(dialog):
    try:
        dialog.isVisible()
        return True
    except RuntimeError:
        return False


def install_live_refresh(dialog):
    dialog._live_data_signature = _data_signature()
    dialog._live_refresh_timer = QTimer(dialog)
    dialog._live_refresh_timer.setSingleShot(True)
    dialog._live_refresh_timer.timeout.connect(lambda: _run_live_refresh(dialog))

    try:
        from ...logic.history_cache import GlobalHistoryCache

        GlobalHistoryCache().signals.context_updated.connect(dialog._on_live_cache_updated)
    except Exception:
        log_swallowed()

    try:
        shortcut = QShortcut(QKeySequence(Qt.Key.Key_F5), dialog)
        shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        shortcut.activated.connect(lambda: refresh_now(dialog, reason="f5"))
        dialog._live_refresh_shortcut = shortcut
    except Exception:
        log_swallowed()


def on_cache_updated(dialog):
    if not _alive(dialog) or not dialog.isVisible():
        return
    sig = _data_signature()
    previous = getattr(dialog, "_live_data_signature", None)
    if sig is None:
        return
    if previous is None:
        # The cache finished loading after the window opened: the window loads
        # its own data, just remember where it stands.
        dialog._live_data_signature = sig
        return
    if sig == previous:
        return  # warmup pass with no new data for this window
    dialog._live_refresh_pending = True
    dialog._live_refresh_timer.start(_DEBOUNCE_MS)


def _busy(dialog):
    if getattr(dialog.deep_dive_manager, "_dd_refresh_in_progress", False):
        return True
    if getattr(dialog.deep_dive_manager, "_build_queue_active", False):
        return True
    if getattr(dialog.deep_dive_manager, "_is_skeleton", False):
        return True
    if getattr(dialog, "layout_anim", None) is not None:
        try:
            from aqt.qt import QAbstractAnimation

            if dialog.layout_anim.state() == QAbstractAnimation.State.Running:
                return True
        except Exception:
            log_swallowed()
    if dialog.isActiveWindow() and QApplication.mouseButtons() != Qt.MouseButton.NoButton:
        return True
    return False


def _run_live_refresh(dialog):
    if not _alive(dialog) or not getattr(dialog, "_live_refresh_pending", False):
        return
    if not dialog.isVisible() or mw.col is None:
        return
    mouse_down = dialog.isActiveWindow() and QApplication.mouseButtons() != Qt.MouseButton.NoButton
    retries = int(getattr(dialog, "_live_refresh_retries", 0) or 0)
    # A stuck "busy" flag must not postpone the reload forever (about 6 s max);
    # a pressed mouse button always waits.
    if mouse_down or (_busy(dialog) and retries < 15):
        dialog._live_refresh_retries = retries + 1
        dialog._live_refresh_timer.start(_BUSY_RETRY_MS)
        return
    dialog._live_refresh_retries = 0
    refresh_now(dialog, reason="data_changed")


def refresh_now(dialog, reason="manual"):
    """Reload tables and the Deep Dive panel, keeping view, tab, deck and period."""
    if not _alive(dialog) or mw.col is None:
        return
    dialog._live_refresh_pending = False
    dialog._live_data_signature = _data_signature()
    try:
        panel_open = hasattr(dialog, "layout_toggle_container") and dialog.layout_toggle_container.isVisible()
        # Saves the current tab and the Deep Dive deck/period; the reload restores
        # them (the same path as reopening the window).
        dialog._save_ui_state()
        dialog.invalidate_view_switch_cache()
        dialog._pending_deep_dive_restore = bool(panel_open)
        try:
            from ...widgets.pinned.widget_factory.utils import PinnedDataManager, invalidate_max_ids_cache

            PinnedDataManager.clear()
            invalidate_max_ids_cache()
        except Exception:
            log_swallowed()
        dialog.refresh_data()
    except Exception:
        log_swallowed()
