# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import copy
import time

from aqt import mw

from .....logic.widget_registry import WidgetRegistry
from .....logic.logger import log_swallowed


def open_time_span_settings(manager):
    from aqt.qt import QDialog
    from .....ui.config import find_visible_settings_dialog
    from .....logic.tabs import get_tabs_config, save_tabs_config

    try:
        existing_cfg = find_visible_settings_dialog()
        if existing_cfg is not None:
            try:
                if hasattr(existing_cfg, "show_tab"):
                    existing_cfg.show_tab("Time Span")
                for i in range(getattr(existing_cfg, "tabs_widget", None) and existing_cfg.tabs_widget.count() or 0):
                    if existing_cfg.tabs_widget.tabText(i).strip().lower() == "time span":
                        existing_cfg.tabs_widget.setCurrentIndex(i)
                        break
                existing_cfg.raise_()
                existing_cfg.activateWindow()
            except Exception:
                log_swallowed()
            return
    except Exception:
        log_swallowed()

    class _TimeSpanConfigHost(QDialog):
        def __init__(self, cfg_manager, parent=None):
            super().__init__(parent)
            self.addon_config = cfg_manager

        def get_tabs_config(self):
            return get_tabs_config(self.addon_config)

        def save_tabs_config(self, tabs_data):
            save_tabs_config(self.addon_config, tabs_data)

        def update_dashboard_visibility(self):
            return

        def refresh_styles(self):
            return

    host = _TimeSpanConfigHost(manager._config_manager, parent=mw)
    from ......web_ui.settings import open_settings_window

    try:
        saved = open_settings_window(host, "Time Span")
    finally:
        host.deleteLater()
    if saved:
        manager.refresh(clear_cache=False)


def open_widget_settings(manager, widget, widget_def):
    from .....ui.config import widget_settings_dialog

    dialog_widget_def = copy.deepcopy(widget_def or {})
    if dialog_widget_def.get("deck_id") in (None, 0, "0"):
        dialog_widget_def["deck_id"] = manager._current_deck_id
    current_cfg = None
    try:
        current_cfg = manager._get_config_manager().config
    except Exception:
        current_cfg = None
    dialog = widget_settings_dialog(dialog_widget_def, parent=widget, global_config=current_cfg)
    accepted = dialog.exec()
    dialog.deleteLater()
    if accepted:
        manager.refresh()


def update_span_bulk(manager, wid, updates):
    merged = dict(updates or {})
    merged["_timespan_token"] = int(time.time() * 1000)
    WidgetRegistry.update_settings_bulk(wid, merged)
    manager.refresh()


# applied by the page to the chart on screen (it reads the setting back once the menu closes): no refresh
_NO_REFRESH = {"binning_override", "show_percent", "fit_to_data", "min_reviews", "review_bars", "review_axis", "rounded"}


def update_setting(manager, wid, key, value):
    WidgetRegistry.update_setting(wid, key, value)
    if key not in _NO_REFRESH:
        manager.refresh()


def _writable_cm(manager):
    cm = getattr(manager, "_config_manager", None)
    if cm is None or not hasattr(cm, "set_value"):
        cm = manager._get_config_manager(force_refresh=True)
        manager._config_manager = cm
    return cm


def toggle_global_bottom_stats(manager, enabled):
    from .....ui import Config

    _writable_cm(manager).set_value(Config.DEEP_DIVE_PINNED_SHOW_BOTTOM_STATS, enabled)
    manager.refresh()


def toggle_global_show_stats(manager, enabled):
    from .....ui import Config

    _writable_cm(manager).set_value(Config.DEEP_DIVE_PINNED_SHOW_STATS, enabled)
    manager.refresh()


def unpin(manager, wid):
    snapshot = WidgetRegistry.removal_snapshot(wid)
    WidgetRegistry.remove(wid)
    manager.refresh()
    if snapshot is not None:
        from .undo_toast import show_undo_toast
        from ......i18n import tr

        show_undo_toast(tr("Widget removed"), lambda: _undo_unpin(manager, snapshot))


def _undo_unpin(manager, snapshot):
    if WidgetRegistry.restore(snapshot):
        manager.refresh()


def reset_widget_size(manager, wid):
    WidgetRegistry.update_setting(wid, "width", None)
    WidgetRegistry.update_setting(wid, "height", None)
    WidgetRegistry.update_setting(wid, "col_span", None)
    manager.refresh()


