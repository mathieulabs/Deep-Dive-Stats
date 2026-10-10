# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .. import Config
from ..theme.icons import get_svg_icon
from ...logic.logger import log_swallowed


def open_settings(dialog, start_tab=None):
    """Open the settings dialog for configuring tabs."""
    try:
        from ..config import find_visible_settings_dialog

        existing_cfg = find_visible_settings_dialog()
        if existing_cfg is not None:
            try:
                if start_tab is not None:
                    target = str(start_tab).strip().lower() if not isinstance(start_tab, int) else None
                    if target:
                        for i in range(existing_cfg.tabs_widget.count()):
                            if existing_cfg.tabs_widget.tabText(i).strip().lower() == target:
                                existing_cfg.tabs_widget.setCurrentIndex(i)
                                break
                existing_cfg.raise_()
                existing_cfg.activateWindow()
            except Exception:
                log_swallowed()
            return
    except Exception:
        log_swallowed()

    try:
        existing = getattr(dialog, "_settings_dialog", None)
        if existing is not None and getattr(existing, "isVisible", lambda: False)():
            try:
                existing.raise_()
                existing.activateWindow()
            except Exception:
                log_swallowed()
            return
    except Exception:
        log_swallowed()

    from ..config import DetailedStatsConfigDialog

    config_dialog = DetailedStatsConfigDialog(dialog)
    dialog._settings_dialog = config_dialog
    try:
        config_dialog.finished.connect(lambda _r=None, dlg=config_dialog: _on_settings_dialog_finished(dialog, dlg))
    except Exception:
        log_swallowed()
    if start_tab is not None:
        try:
            if isinstance(start_tab, int):
                idx = max(0, min(config_dialog.tabs_widget.count() - 1, int(start_tab)))
                config_dialog.tabs_widget.setCurrentIndex(idx)
            else:
                target = str(start_tab).strip().lower()
                for i in range(config_dialog.tabs_widget.count()):
                    if config_dialog.tabs_widget.tabText(i).strip().lower() == target:
                        config_dialog.tabs_widget.setCurrentIndex(i)
                        break
        except Exception:
            log_swallowed()
    if config_dialog.exec():
        dialog.invalidate_view_switch_cache()
        if dialog.view_mode == "time":
            dialog.load_tabs()
        else:
            dialog.load_deck_view()


def _on_settings_dialog_finished(dialog, dlg):
    try:
        cur = getattr(dialog, "_settings_dialog", None)
        if cur is dlg:
            dialog._settings_dialog = None
    except Exception:
        log_swallowed()


def open_deck_options(dialog):
    """Open dialog for deck exclusion and coloring."""
    from ..config import DeckSettingsDialog

    before = sorted((dialog.addon_config.config.get(Config.EXCLUDED_DECKS, []) or []), key=str)
    before_dates = list(dialog.addon_config.config.get(Config.EXCLUDED_DATES, []) or [])
    dlg = DeckSettingsDialog(dialog.addon_config, dialog)
    if dlg.exec():
        after = sorted((dialog.addon_config.config.get(Config.EXCLUDED_DECKS, []) or []), key=str)
        after_dates = list(dialog.addon_config.config.get(Config.EXCLUDED_DATES, []) or [])
        if after != before or after_dates != before_dates:
            # The all-decks aggregates of the cache depend on the exclusion list.
            try:
                from ...logic.history_cache import GlobalHistoryCache
                from ...widgets.pinned.widget_factory.utils import PinnedDataManager
                GlobalHistoryCache.clear_all_cache()
                PinnedDataManager.clear()
            except Exception:
                log_swallowed()
        dialog.invalidate_view_switch_cache()
        if dialog.view_mode == "time":
            dialog.load_tabs()
        else:
            dialog.load_deck_view()


def toggle_view(dialog):
    """Toggle between time-range view and deck view."""
    if dialog.view_mode == "time":
        dialog.view_mode = "deck"
        dialog.view_toggle_btn.setText(" View by Time")
        dialog.view_toggle_btn.setIcon(get_svg_icon("calendar", context_ref=dialog))
        dialog.search_bar.setPlaceholderText("Search decks...")
        dialog._initial_deck_selected = False
        dialog.load_deck_view(prefer_cached=True)
    else:
        dialog.view_mode = "time"
        dialog.view_toggle_btn.setText(" View by Deck")
        dialog.view_toggle_btn.setIcon(get_svg_icon("activity", context_ref=dialog))
        dialog.search_bar.setPlaceholderText("Filter rows...")
        dialog.load_tabs(prefer_cached=True)

    if hasattr(dialog, "search_bar"):
        dialog._on_search_text_changed(dialog.search_bar.text())

    dialog.addon_config.config[Config.DETAILS_VIEW_MODE] = dialog.view_mode
    dialog.addon_config.write_config()
    dialog.refresh_ui_icons()
