# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from aqt import mw
from aqt.qt import QVBoxLayout, QWidget

from .stream import start_deck_streaming
from ...logic.logger import log_swallowed


def restore_deck_view_from_cache(
    dialog,
    cache,
    *,
    add_folder_tab_buttons_fn,
    is_deck_tab_visible_fn,
    refresh_deck_tab_header_styles_fn,
    populate_deck_tab_fn,
    on_tab_expand_clicked_fn,
):
        """Restore Deck View from an in-memory snapshot (no background fetch)."""
        ui_tabs = cache.get("ui_tabs") or []
        if ui_tabs:
            dialog.tab_widget.clear()
            dialog.tab_stats = dict(cache.get("tab_stats") or {})
            dialog.deck_view_data = dict(cache.get("deck_view_data") or {})
            dialog._deck_tabs_populated = set()
            dialog._deck_fetch_queue = []

            tab_widget = dialog.tab_widget
            visible_indices = []
            for entry in ui_tabs:
                w = entry.get("widget")
                if w is None:
                    continue
                tab_index = tab_widget.count()
                tab_widget.addTab(w, entry.get("title", ""))
                is_visible = bool(entry.get("visible", True))
                tab_widget.setTabVisible(tab_index, is_visible)
                if is_visible:
                    visible_indices.append(tab_index)
                if entry.get("is_folder"):
                    add_folder_tab_buttons_fn(dialog, tab_index, entry.get("full_name", entry.get("title", "")))

            selected = False
            target_did = getattr(dialog, 'target_deck_id', None)
            if target_did is not None:
                for i in range(tab_widget.count()):
                    w = tab_widget.widget(i)
                    if w and str(w.property("deck_id")) == str(target_did):
                        tab_widget.setCurrentIndex(i)
                        selected = True
                        break
            if not selected:
                selected_deck_id = cache.get("selected_deck_id")
                if selected_deck_id is not None:
                    for i in range(tab_widget.count()):
                        w = tab_widget.widget(i)
                        if w and str(w.property("deck_id")) == str(selected_deck_id):
                            tab_widget.setCurrentIndex(i)
                            selected = True
                            break
            if not selected:
                saved_idx = getattr(dialog, '_saved_deck_tab', 0)
                if 0 <= saved_idx < tab_widget.count() and tab_widget.isTabVisible(saved_idx):
                    tab_widget.setCurrentIndex(saved_idx)
                    selected = True
            if not selected and visible_indices:
                tab_widget.setCurrentIndex(visible_indices[0])

            idx = tab_widget.currentIndex()
            if idx >= 0:
                tab = tab_widget.widget(idx)
                deck_id = tab.property("deck_id") if tab else None
                if deck_id in dialog.deck_view_data:
                    populate_deck_tab_fn(dialog, idx, do_resize=True, from_tab_change=True)
            refresh_deck_tab_header_styles_fn(dialog)
            dialog._tab_widget_view_kind = "deck"
            dialog.on_tab_changed(tab_widget.currentIndex())
            return True

        deck_tree = [dict(d) for d in (cache.get("deck_tree") or [])]
        if not deck_tree:
            return False

        dialog.tab_widget.clear()
        dialog.tab_stats = dict(cache.get("tab_stats") or {})
        dialog.deck_view_data = dict(cache.get("deck_view_data") or {})
        dialog._deck_tabs_populated = set()
        dialog._deck_fetch_queue = []

        tab_widget = dialog.tab_widget
        visible_indices = []

        for deck_info in deck_tree:
            did = deck_info["did"]
            tab_name = deck_info["name"]
            depth = deck_info.get("depth", 0)
            is_folder = bool(deck_info.get("is_folder", False))

            tab = QWidget(tab_widget)
            tab_layout = QVBoxLayout(tab)
            tab_layout.setContentsMargins(0, 0, 0, 0)
            tab.setProperty("deck_id", did)
            tab.setProperty("full_name", deck_info.get("full_name", tab_name))
            tab.setProperty("is_folder", is_folder)
            tab.setProperty("depth", depth)

            tab_index = tab_widget.count()
            tab_widget.addTab(tab, tab_name)
            is_visible = is_deck_tab_visible_fn(dialog, deck_info.get("full_name", tab_name), tab_name, did)
            if not is_visible:
                tab_widget.setTabVisible(tab_index, False)
            else:
                visible_indices.append(tab_index)

            if is_folder:
                add_folder_tab_buttons_fn(dialog, tab_index, deck_info["full_name"])

        selected = False
        target_did = getattr(dialog, 'target_deck_id', None)
        if target_did is not None:
            for i in range(tab_widget.count()):
                w = tab_widget.widget(i)
                if w and str(w.property("deck_id")) == str(target_did):
                    tab_widget.setCurrentIndex(i)
                    selected = True
                    break

        if not selected:
            saved_idx = getattr(dialog, '_saved_deck_tab', 0)
            if 0 <= saved_idx < tab_widget.count() and tab_widget.isTabVisible(saved_idx):
                tab_widget.setCurrentIndex(saved_idx)
                selected = True

        if not selected and visible_indices:
            tab_widget.setCurrentIndex(visible_indices[0])

        idx = tab_widget.currentIndex()
        if idx >= 0:
            tab = tab_widget.widget(idx)
            deck_id = tab.property("deck_id") if tab else None
            if deck_id in dialog.deck_view_data:
                populate_deck_tab_fn(dialog, idx, do_resize=True, from_tab_change=True)
        refresh_deck_tab_header_styles_fn(dialog)
        dialog._tab_widget_view_kind = "deck"
        dialog.on_tab_changed(tab_widget.currentIndex())
        return True



def load_deck_view(
    dialog,
    prefer_cached=False,
    *,
    restore_deck_view_from_cache_fn,
    build_deck_tree_fn,
    add_folder_tab_buttons_fn,
    is_deck_tab_visible_fn,
    populate_deck_tab_fn,
    on_tab_expand_clicked_fn,
    refresh_deck_tab_header_styles_fn,
    deleted_tab_did,
):
        """Load deck view - tabs are decks, rows are time ranges.
        Uses a single background task for all decks to maximize performance.
        """
        dialog.load_generation += 1
        gen = dialog.load_generation

        if getattr(dialog, "_tab_widget_view_kind", None) == "time":
            try:
                from ...logic.tabs import stash_time_tabs_for_restore
                stash_time_tabs_for_restore(dialog)
            except Exception:
                log_swallowed()

        cache = getattr(dialog, "_deck_view_cache", None)
        cache_has_snapshot = bool(cache and cache.get("deck_tree"))
        cache_has_data = bool(cache and cache.get("deck_view_data"))
        if prefer_cached and cache_has_snapshot and cache_has_data:
            if restore_deck_view_from_cache_fn(dialog, cache):
                return

        dialog._tab_widget_view_kind = "deck"
        dialog.tab_widget.clear()
        dialog.tab_stats = {}
        dialog.deck_view_data = {}
        dialog._deck_tabs_populated = set()

        from ...logic.tabs import get_tabs_config
        tabs_config = [t for t in get_tabs_config(dialog.addon_config) if t.get("enabled", True)]

        from ...logic.history_cache import GlobalHistoryCache
        ghc = GlobalHistoryCache()
        if ghc.is_initialized:
            from ...logic.data import fetch_dids_with_data
            all_dids = fetch_dids_with_data()
        else:
            all_dids = []

        deck_tree = build_deck_tree_fn(dialog, all_dids, deleted_tab_did=deleted_tab_did)
        dialog._deck_view_cache = {
            "complete": False,
            "deck_tree": [dict(d) for d in deck_tree],
            "deck_view_data": {},
            "tab_stats": {},
        }

        tab_widget = dialog.tab_widget
        tab_bar = tab_widget.tabBar()
        tab_bar.setMovable(False)
        prev_updates_enabled = tab_widget.updatesEnabled()
        prev_bar_updates_enabled = tab_bar.updatesEnabled()
        prev_blocked = tab_widget.blockSignals(True)
        tab_widget.setUpdatesEnabled(False)
        tab_bar.setUpdatesEnabled(False)
        visible_indices = []

        for deck_info in deck_tree:
            if dialog.load_generation != gen: return

            did = deck_info["did"]
            tab_name = deck_info["name"]
            depth = deck_info["depth"]
            is_folder = deck_info["is_folder"]

            tab = QWidget(tab_widget)
            tab_layout = QVBoxLayout(tab)
            tab_layout.setContentsMargins(0, 0, 0, 0)
            tab.setProperty("deck_id", did)
            tab.setProperty("full_name", deck_info.get("full_name", tab_name))
            tab.setProperty("is_folder", is_folder)
            tab.setProperty("depth", depth)

            tab_index = tab_widget.count()
            tab_widget.addTab(tab, tab_name)
            is_visible = is_deck_tab_visible_fn(dialog, deck_info.get("full_name", tab_name), tab_name, did)
            if not is_visible:
                tab_widget.setTabVisible(tab_index, False)
            else:
                visible_indices.append(tab_index)

            # Keep native tab text (so it follows the same centered style as View by Time),
            # and only inject folder affordances on tab sides.
            if is_folder:
                add_folder_tab_buttons_fn(dialog, tab_index, deck_info["full_name"])
        tab_widget.blockSignals(prev_blocked)
        tab_widget.setUpdatesEnabled(prev_updates_enabled)
        tab_bar.setUpdatesEnabled(prev_bar_updates_enabled)

        # Auto-select the target deck before starting the streaming queue so the
        # first fetch can prioritize what the user is actually looking at.
        target_did = getattr(dialog, 'target_deck_id', None)
        target_name = None
        selected = False

        if target_did:
            all_decks = mw.col.decks.all_names_and_ids()
            try:
                int_did = int(target_did)
                target_name = next((d.name for d in all_decks if d.id == int_did), None)
                target_did = int_did
            except (ValueError, TypeError):
                target_name = target_did
                found_d = next((d for d in all_decks if d.name == target_name), None)
                if found_d:
                    target_did = found_d.id

            for i in range(tab_widget.count()):
                w = tab_widget.widget(i)
                if w and str(w.property("deck_id")) == str(target_did):
                    tab_widget.setCurrentIndex(i)
                    selected = True
                    break

            if not selected and target_name:
                for i in range(tab_widget.count()):
                    w = tab_widget.widget(i)
                    if w and w.property("full_name") == target_name:
                        tab_widget.setCurrentIndex(i)
                        selected = True
                        break

            if not selected and target_name:
                parts = target_name.split("::")
                for j in range(len(parts) - 1, 0, -1):
                    parent_path = "::".join(parts[:j])
                    for i in range(tab_widget.count()):
                        w = tab_widget.widget(i)
                        if w and w.property("full_name") == parent_path:
                            tab_widget.setCurrentIndex(i)
                            selected = True

                            if parent_path not in dialog.expanded_decks:
                                on_tab_expand_clicked_fn(dialog, i, parent_path)
                            break
                    if selected:
                        break

        if not selected:
            saved_idx = getattr(dialog, '_saved_deck_tab', 0)
            if 0 <= saved_idx < tab_widget.count() and tab_widget.isTabVisible(saved_idx):
                tab_widget.setCurrentIndex(saved_idx)
                selected = True

        if not selected and visible_indices:
            tab_widget.setCurrentIndex(visible_indices[0])

        show_trends = dialog.trend_toggle.isChecked() if hasattr(dialog, 'trend_toggle') else False
        dialog.deck_view_data = {}

        start_deck_streaming(
            dialog=dialog,
            gen=gen,
            deck_tree=deck_tree,
            tab_widget=tab_widget,
            tabs_config=tabs_config,
            show_trends=show_trends,
            deleted_tab_did=deleted_tab_did,
            populate_deck_tab_fn=populate_deck_tab_fn,
        )

        refresh_deck_tab_header_styles_fn(dialog)


        dialog.on_tab_changed(dialog.tab_widget.currentIndex())

