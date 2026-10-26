# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QTimer

from ..imports import mw
from .....logic.logger import log_swallowed


def show_overlay(manager, settle_ms):
    """Show the pinned widgets, unless Anki has left the deck list or the deck screen
    meanwhile. They sit on the main web view, which is also the review screen: a show
    deferred from the deck list (Ctrl+Z there opens the review again) put them over the
    card."""
    overlay = manager._overlay
    if not overlay or mw.state not in ("deckBrowser", "overview"):
        return
    overlay.show()
    overlay.setProperty("needs_init_geom", True)
    manager.sync_overlay()
    manager._settle_sync_timer.start(settle_ms)


def finalize_rebuild(manager, has_widgets, overview_light_mode, review_return_light_mode, review_return_phase_b_mode, should_full_rebuild, deck_id):
    if has_widgets:
        if review_return_light_mode and not review_return_phase_b_mode:
            if manager._overlay:
                manager._overlay.hide()
                manager._overlay.setProperty("needs_init_geom", False)
            return
        if overview_light_mode or review_return_light_mode:
            # Defer show and geometry sync by one tick to keep the entry frame light: _overlay.show() synchronously flushes Qt layout events for all children (~35ms with 9 widgets).
            def _deferred_show():
                if not manager._overlay:
                    return
                try:
                    manager._clear_browser_heatmap_snapshot_overlay()
                except Exception:
                    log_swallowed()
                show_overlay(manager, 320)
            QTimer.singleShot(0, _deferred_show)
        else:
            try:
                manager._clear_browser_heatmap_snapshot_overlay()
            except Exception:
                log_swallowed()
            # Synced right away to render the patches; the JS message can come late.
            show_overlay(manager, 220)

        # Apply the theme to all widgets after a rebuild, except in phase A of review return: stat cards are stale anyway and phase B refreshes styles with correct data.
        if not review_return_light_mode or review_return_phase_b_mode:
            from ..runtime.style_update import update_styles_after_rebuild

            QTimer.singleShot(0, lambda: update_styles_after_rebuild(manager))
    else:
        try:
            manager._clear_browser_heatmap_snapshot_overlay()
        except Exception:
            log_swallowed()
        manager._overlay.hide()
        manager._update_placeholder_height(0)



