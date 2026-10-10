# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QPushButton, QTableWidget

from .. import Config
from ..theme.icons import get_svg_icon
from ...logic.logger import log_swallowed


def prioritize_deck_tab(dialog, index):
    """Move a specific tab's deck to the front of the streaming fetch queue."""
    if not hasattr(dialog, "_deck_fetch_queue") or not dialog._deck_fetch_queue:
        return

    tab = dialog.tab_widget.widget(index)
    if not tab:
        return

    did = tab.property("deck_id")
    if did in dialog._deck_fetch_queue:
        dialog._deck_fetch_queue.remove(did)
        dialog._deck_fetch_queue.insert(0, did)


def persist_expanded_decks(dialog):
    """Save which deck folders are open. Time view and deck view share this one state,
    so the snapshots kept for fast view switching are dropped: they hold the old state."""
    dialog.addon_config.set_value(Config.DETAILS_EXPANDED_DECKS, sorted(dialog.expanded_decks))
    dialog.addon_config.set_value(Config.DETAILS_EXPANDED_DECKS_SET, True)
    try:
        dialog.invalidate_view_switch_cache()
    except Exception:
        log_swallowed()


def on_tab_expand_clicked(dialog, index, full_path, refresh_deck_tab_header_styles_fn):
    if full_path in dialog.expanded_decks:
        dialog.expanded_decks.remove(full_path)
    else:
        dialog.expanded_decks.add(full_path)

    persist_expanded_decks(dialog)

    container = dialog.tab_widget.tabBar().tabButton(
        index, dialog.tab_widget.tabBar().ButtonPosition.LeftSide
    )
    if container:
        btn = container.findChild(QPushButton)
        if btn:
            btn.setIcon(
                get_svg_icon(
                    "chevron-down" if full_path in dialog.expanded_decks else "chevron-right"
                )
            )

    refresh_deck_tab_visibility(dialog)
    refresh_deck_tab_header_styles_fn(dialog)


def refresh_deck_tab_visibility(dialog):
    """Update visibility of tabs based on hierarchy and expansion state."""
    text = dialog.search_bar.text().lower() if hasattr(dialog, "search_bar") else ""
    current_idx = dialog.tab_widget.currentIndex()
    visible_indices = []

    for i in range(dialog.tab_widget.count()):
        tab = dialog.tab_widget.widget(i)
        full_name = tab.property("full_name")
        if not full_name:
            continue

        visible = True
        parts = full_name.split("::")
        for j in range(1, len(parts)):
            ancestor = "::".join(parts[:j])
            if ancestor not in dialog.expanded_decks:
                visible = False
                break

        if text:
            tab_text = dialog.tab_widget.tabText(i).lower()
            did_str = str(tab.property("deck_id") or "").lower()
            if text not in tab_text and text not in did_str:
                visible = False

        dialog.tab_widget.setTabVisible(i, visible)
        if visible:
            visible_indices.append(i)

    if current_idx >= 0 and not dialog.tab_widget.isTabVisible(current_idx) and visible_indices:
        next_idx = next((idx for idx in visible_indices if idx > current_idx), visible_indices[0])
        dialog.tab_widget.setCurrentIndex(next_idx)
        current_idx = next_idx

    if current_idx >= 0 and dialog.tab_widget.isTabVisible(current_idx):
        tab = dialog.tab_widget.widget(current_idx)
        table = tab.findChild(QTableWidget)
        if table:
            from ..details_dialog import auto_resize_window

            if auto_resize_window(dialog, table, resize_window=False):
                table._has_been_resized = True


