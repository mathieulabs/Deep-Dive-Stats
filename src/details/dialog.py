# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from aqt import mw
from aqt.qt import QDialog, Qt, QIcon

from ..const import Period, LOGO_PNG
from ..config import Config

from .logic.tabs import load_tabs, save_tabs_config, get_tabs_config, get_active_tabs_config
from .ui.deep_dive import DeepDiveManager
from .ui.deck_view import load_deck_view
from .ui.details_dialog import setup_dialog_ui, auto_resize_window
from .ui.dialog.lifecycle import (
    apply_layout_state as apply_layout_state_impl,
    close_event as close_event_impl,
    on_deep_dive_closed as on_deep_dive_closed_impl,
    resize_event as resize_event_impl,
    save_ui_state as save_ui_state_impl,
    show_event as show_event_impl,
    switch_layout as switch_layout_impl,
    toggle_side_view as toggle_side_view_impl,
    update_responsive_toolbar as update_responsive_toolbar_impl,
)
from .ui.interactions import (
    on_cell_clicked, on_cell_double_clicked, on_tab_changed,
    on_trend_toggled, on_search_text_changed, filter_deck_tabs,
    on_visual_buttons_toggled, on_retention_spark_toggled, on_visual_option_toggled
)
from .ui.table import on_header_clicked as on_header_clicked_impl
from .ui.table import repopulate_current_table as repopulate_current_table_impl
from .ui.dialog.tab_restore import handle_post_tab_change
from .ui.dialog.settings import (
    _on_settings_dialog_finished as on_settings_dialog_finished_impl,
    open_deck_options as open_deck_options_impl,
    open_settings as open_settings_impl,
    toggle_view as toggle_view_impl,
)


class DetailedStatsDialog(QDialog):
    def __init__(self, addon_config, parent=None):

        # No Qt parent: a child window of mw gets no taskbar button of its own on Windows.
        super().__init__(None)
        self._anki_parent = parent
        self.addon_config = addon_config
        
        # A Window instead of a Dialog keeps it modeless with its own taskbar entry.
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowMinMaxButtonsHint | Qt.WindowType.WindowCloseButtonHint)
        from ..config import dev_label

        self.setWindowTitle(dev_label("Deep Dive Stats"))
        self.setWindowIcon(QIcon(LOGO_PNG))
        
        self.tab_stats = {} # {tab_index: stats_dict}
        self.view_mode = self.addon_config.config.get(Config.DETAILS_VIEW_MODE, 'time') # 'time' or 'deck'
        self.expanded_decks = set(self.addon_config.config.get(Config.DETAILS_EXPANDED_DECKS, []))
        self.side_view = self.addon_config.config.get(Config.DETAILS_SIDE_VIEW, False)
        self.layout_state = self.addon_config.config.get(Config.DETAILS_LAYOUT_STATE, 1)
        self.layout_anim = None
        self._last_horizontal_scroll = 0
        self._saved_time_tab = self.addon_config.config.get(Config.DETAILS_TIME_TAB_INDEX, 0)
        self._saved_deck_tab = self.addon_config.config.get(Config.DETAILS_DECK_TAB_INDEX, 0)
        # Target deck: Always start with the currently selected deck in Anki
        try:
            current_deck = mw.col.decks.current()
            self.target_deck_id = current_deck.get('id') if current_deck else None
            self.target_deck_name = current_deck.get('name') if current_deck else None
        except Exception:
            self.target_deck_id = None
            self.target_deck_name = None
            
        # Target time span: Use previously active period in Deep Dive, or fallback to the current Time view tab's span
        self.target_time_span = self.addon_config.config.get(Config.DETAILS_DEEP_DIVE_PERIOD_RANGE)
        if self.target_time_span is None:
            tabs_config = self.get_active_tabs_config()
            if 0 <= self._saved_time_tab < len(tabs_config):
                self.target_time_span = tabs_config[self._saved_time_tab].get("range", Period.WEEK)
            else:
                self.target_time_span = Period.WEEK
                
        self._pending_deep_dive_restore = True
        
        # Override config identifier/range for deep dive open logic with our target
        self.addon_config.config[Config.DETAILS_DEEP_DIVE_IDENTIFIER] = self.target_deck_id
        if getattr(self, 'target_deck_name', None):
             self.addon_config.config[Config.DETAILS_DEEP_DIVE_TITLE] = self.target_deck_name
        self.addon_config.config[Config.DETAILS_DEEP_DIVE_PERIOD_RANGE] = self.target_time_span

        
        # Done before the background warm-up starts: these main-thread collection
        # calls would otherwise wait for a background query.
        # An empty saved list only means "everything closed" once the user has toggled a folder.
        if not self.expanded_decks and not self.addon_config.config.get(Config.DETAILS_EXPANDED_DECKS_SET, False):
            all_dids = {d.id: d.name for d in mw.col.decks.all_names_and_ids()}
            from .logic.data import fetch_dids_with_data
            for did in fetch_dids_with_data():
                if did and did in all_dids:
                    full_name = all_dids[did]
                    parts = full_name.split("::")
                    for i in range(1, len(parts)):
                        self.expanded_decks.add("::".join(parts[:i]))
        
        self.deep_dive_manager = DeepDiveManager(self)
        self.expanded_header_controls = None
        self.load_generation = 0 # Track active load request to abort stale timers/tasks
        from .logic.data import warm_time_view_static_bundle_async
        warm_time_view_static_bundle_async(
            self.addon_config.config.get(Config.EXCLUDED_DECKS, []),
            generation_key="dialog_init",
        )
        
        self.setup_ui()
        self.deep_dive_manager.warm_up()

        self.apply_layout_state(animated=False)

        self._sort_col = 1
        self._sort_order = Qt.SortOrder.DescendingOrder
        
        if self.view_mode == 'deck':
            self.load_deck_view()
        else:
            self.load_tabs()
            
        screen = mw.screen()
        if not screen:
            screen = mw.app.primaryScreen()
        geom = screen.availableGeometry()
        
        target_w = int(geom.width() * 0.85)
        target_h = int(geom.height() * 0.85)
        self.resize(target_w, target_h)
        
        # Substantial minimum size but capped by screen to avoid overflow
        min_w = min(850, geom.width() - 40)
        min_h = min(600, geom.height() - 40)
        self.setMinimumSize(min_w, min_h)
        # Reserve the final splitter space before first paint to avoid the top dashboard
        # temporarily expanding into the deep-dive/table area.
        self.apply_layout_state(animated=False)
        
        from .logic.history_cache import GlobalHistoryCache
        GlobalHistoryCache.init_async()

        # Reload in place when the collection changes while the window is open.
        from .ui.dialog.live_refresh import install_live_refresh
        install_live_refresh(self)

    def _on_live_cache_updated(self):
        from .ui.dialog.live_refresh import on_cache_updated
        on_cache_updated(self)
            
    def setup_ui(self):
        setup_dialog_ui(self)

    def showEvent(self, event):
        return show_event_impl(self, event)

    def _save_ui_state(self):
        return save_ui_state_impl(self)

    def closeEvent(self, event):
        return close_event_impl(self, event)

    def refresh_styles(self):
        from .ui.details_dialog.theme_runtime import refresh_styles as _impl

        return _impl(self)

    def refresh_ui_icons(self):
        from .ui.details_dialog.theme_runtime import refresh_ui_icons as _impl

        return _impl(self)

    def update_dashboard_visibility(self):
        from .ui.details_dialog.theme_runtime import update_dashboard_visibility as _impl

        return _impl(self)

    def toggle_side_view(self):
        return toggle_side_view_impl(self)

    def on_deep_dive_closed(self):
        return on_deep_dive_closed_impl(self)


    def switch_layout(self, state):
        return switch_layout_impl(self, state)

    def apply_layout_state(self, state=None, update_sizes=True, animated=True):
        return apply_layout_state_impl(self, state=state, update_sizes=update_sizes, animated=animated)
        
    def _clear_layout(self, layout):
        """Recursively clear a layout and delete all widgets."""
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                elif item.layout():
                    self._clear_layout(item.layout())
            layout.deleteLater()



    def resizeEvent(self, event):
        return resize_event_impl(self, event)

    def changeEvent(self, event):
        QDialog.changeEvent(self, event)
        from .ui.dialog.screen_fit import on_change

        on_change(self, event)

    def _update_responsive_toolbar(self):
        return update_responsive_toolbar_impl(self)

    def get_tabs_config(self):
        return get_tabs_config(self.addon_config)

    def get_active_tabs_config(self):
        """Enabled time spans only: their position is the index of the tab in the window."""
        return get_active_tabs_config(self.addon_config)

    def save_tabs_config(self, tabs_data):
        save_tabs_config(self.addon_config, tabs_data)

    def load_tabs(self, prefer_cached=False, reason="direct", force=False):
        load_tabs(self, prefer_cached=prefer_cached)

    def load_deck_view(self, prefer_cached=False, reason="direct", force=False):
        load_deck_view(self, prefer_cached=prefer_cached)

    def invalidate_view_switch_cache(self):
        """Invalidate cross-view UI snapshots used for fast mode switching."""
        self._time_view_cache = None
        self._deck_view_cache = None

    def refresh_data(self):
        """Force a full data reload and UI refresh."""
        if self.view_mode == 'deck':
            self.load_deck_view()
        else:
            self.deep_dive_manager.warm_up()
            self.load_tabs()

    def auto_resize_window(self, table, resize_window=True):
        """Auto-resize columns and window width to fit content."""
        return auto_resize_window(self, table, resize_window)


    
    def open_settings(self, start_tab=None):
        return open_settings_impl(self, start_tab=start_tab)

    def _on_settings_dialog_finished(self, dlg):
        return on_settings_dialog_finished_impl(self, dlg)

    def open_deck_options(self):
        return open_deck_options_impl(self)

    def toggle_view(self):
        return toggle_view_impl(self)


    def _repopulate_current_table(self):
        return repopulate_current_table_impl(self)

    def on_header_clicked(self, table, col_idx):
        return on_header_clicked_impl(self, table, col_idx)


    def on_cell_double_clicked(self, row, col):
        on_cell_double_clicked(self, row, col)

    def on_cell_clicked(self, row, col):
        on_cell_clicked(self, row, col)

    def on_tab_changed(self, index):
        on_tab_changed(self, index)
        handle_post_tab_change(self, index)

    def on_trend_toggled(self, checked):
        on_trend_toggled(self, checked)

    def _on_search_text_changed(self, text):
        on_search_text_changed(self, text)

    def filter_deck_tabs(self, text):
        filter_deck_tabs(self, text)

    def on_visual_buttons_toggled(self, state):
        on_visual_buttons_toggled(self, state)

    def on_visual_option_toggled(self, key, value):
        on_visual_option_toggled(self, key, value)

    def on_retention_spark_toggled(self, state):
        on_retention_spark_toggled(self, state)

    def _on_horizontal_scroll_changed(self, value):
        """Update the global horizontal scroll position to keep tabs in sync."""
        self._last_horizontal_scroll = value








