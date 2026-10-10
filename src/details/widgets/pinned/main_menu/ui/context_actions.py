# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import copy
import time

from aqt import mw

from ...store.registry import WidgetRegistry
from .....logic.logger import log_swallowed


def show_context_menu(manager, widget, widget_id, pos):
    all_defs = WidgetRegistry.get_all()
    widget_def = next((d for d in all_defs if d.get("id") == widget_id), None)
    if not widget_def:
        return
    manager._context_menu.show(widget, widget_def, pos)


def open_details_dialog():
    from ..... import open_details_dialog as _open_details_dialog

    _open_details_dialog()


def open_time_span_settings(manager):
    from aqt.qt import QDialog
    from .....ui.config import DetailedStatsConfigDialog, find_visible_settings_dialog
    from .....logic.tabs import get_tabs_config, save_tabs_config

    try:
        existing_cfg = find_visible_settings_dialog()
        if existing_cfg is not None:
            try:
                for i in range(existing_cfg.tabs_widget.count()):
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
    dlg = DetailedStatsConfigDialog(host)
    try:
        for i in range(dlg.tabs_widget.count()):
            if dlg.tabs_widget.tabText(i).strip().lower() == "time span":
                dlg.tabs_widget.setCurrentIndex(i)
                break
    except Exception:
        log_swallowed()
    if dlg.exec():
        from .....logic.tabs import refresh_open_details_tabs

        refresh_open_details_tabs()
        manager.refresh(clear_cache=False)


def open_widget_settings(manager, widget, widget_def):
    from .....ui.config import WidgetSettingsDialog

    dialog_widget_def = copy.deepcopy(widget_def or {})
    if dialog_widget_def.get("deck_id") in (None, 0, "0"):
        dialog_widget_def["deck_id"] = manager._current_deck_id
    current_cfg = None
    try:
        current_cfg = manager._get_config_manager().config
    except Exception:
        current_cfg = None
    dialog = WidgetSettingsDialog(dialog_widget_def, parent=widget, global_config=current_cfg)
    accepted = dialog.exec()
    dialog.deleteLater()
    if accepted:
        manager._last_state = None
        manager._last_widget_set = None
        manager.refresh()


def update_span(manager, wid, span):
    WidgetRegistry.update_settings_bulk(wid, {
        "time_span": int(span) if span is not None else None,
        "_timespan_token": int(time.time() * 1000),
    })
    manager._last_state = None
    manager.refresh()


def update_span_bulk(manager, wid, updates):
    merged = dict(updates or {})
    merged["_timespan_token"] = int(time.time() * 1000)
    WidgetRegistry.update_settings_bulk(wid, merged)
    manager._last_state = None
    manager.refresh()


def update_setting(manager, wid, key, value):
    WidgetRegistry.update_setting(wid, key, value)
    manager._last_state = None
    if key == "show_stats":
        manager._last_widget_set = None

    if key == "binning_override":
        widget = manager._active_widgets.get(wid)
        if widget:
            from aqt.qt import QWidget
            for child in widget.findChildren(QWidget):
                if hasattr(child, "binning_override") and hasattr(child, "binning_active"):
                    child.binning_override = value
                    if hasattr(child, "_invalidate_data_caches"):
                        child._invalidate_data_caches()
                    elif hasattr(child, "_invalidate_caches"):
                        child._invalidate_caches()
                    elif hasattr(child, "update_data"):
                        child.update_data(child.data_dict)
                    child.update()
        return

    if key == "fit_to_data":
        widget = manager._active_widgets.get(wid)
        if widget:
            from aqt.qt import QWidget
            for child in widget.findChildren(QWidget):
                if hasattr(child, "set_fit_to_data"):
                    child.set_fit_to_data(bool(value))
        return

    if key in ("min_reviews", "review_bars", "review_axis", "rounded"):
        widget = manager._active_widgets.get(wid)
        if widget:
            from aqt.qt import QWidget
            for child in widget.findChildren(QWidget):
                if key == "min_reviews" and hasattr(child, "set_min_reviews"):
                    child.set_min_reviews(value)
                elif key == "review_bars" and hasattr(child, "set_review_bars"):
                    child.set_review_bars(bool(value))
                elif key == "review_axis" and hasattr(child, "set_review_axis"):
                    child.set_review_axis(bool(value))
                elif key == "rounded" and hasattr(child, "set_rounded"):
                    child.set_rounded(bool(value))
        return

    manager.refresh()


def _writable_cm(manager):
    cm = getattr(manager, "_config_manager", None)
    if cm is None or not hasattr(cm, "set_value"):
        cm = manager._get_config_manager(force_refresh=True)
        manager._config_manager = cm
    return cm


def toggle_global_bottom_stats(manager, enabled):
    from ..imports import Config

    _writable_cm(manager).set_value(Config.DEEP_DIVE_PINNED_SHOW_BOTTOM_STATS, enabled)
    for wid in list(manager._active_widgets.keys()):
        manager._active_widgets[wid].deleteLater()
    manager._active_widgets = {}
    manager._widget_update_signatures = {}
    manager._last_widget_set = None
    manager.refresh()


def toggle_global_show_stats(manager, enabled):
    from ..imports import Config

    _writable_cm(manager).set_value(Config.DEEP_DIVE_PINNED_SHOW_STATS, enabled)
    for wid in list(manager._active_widgets.keys()):
        manager._active_widgets[wid].deleteLater()
    manager._active_widgets = {}
    manager._widget_update_signatures = {}
    manager._last_widget_set = None
    manager.refresh()


def unpin(manager, wid):
    WidgetRegistry.remove(wid)
    manager.refresh()


def reset_widget_size(manager, wid):
    WidgetRegistry.update_setting(wid, "width", None)
    WidgetRegistry.update_setting(wid, "height", None)
    WidgetRegistry.update_setting(wid, "col_span", None)
    manager._widget_update_signatures.pop(wid, None)
    widget = manager._active_widgets.get(wid)
    if widget and hasattr(widget, "apply_size"):
        widget.apply_size(None, None)
        if widget.parentWidget() and widget.parentWidget().layout():
            widget.parentWidget().layout().activate()
    manager._last_widget_set = None
    manager._last_state = None
    manager.refresh()





