# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations

from typing import TYPE_CHECKING

from aqt import mw

from ... import Config
from ... import ConfigManager
from .persistence_keys import (
    DASHBOARD_UNLINK_STYLE_KEYS,
    PINNED_UNLINK_STYLE_KEYS,
    WIDGET_BEHAVIOR_KEYS,
)
from ....logic.logger import log_swallowed

if TYPE_CHECKING:
    from ..dialogs.widget_settings import WidgetSettingsDialog


def persist_widget_settings(dialog: "WidgetSettingsDialog") -> None:
    if dialog.is_pinned_mode:
        _persist_pinned_widget_settings(dialog)
        return
    if dialog.is_dashboard_context:
        _persist_dashboard_widget_settings(dialog)


def _persist_pinned_widget_settings(dialog: "WidgetSettingsDialog") -> None:
    manager = ConfigManager(mw)
    cfg = dict(manager.config)

    if not dialog.is_unlinked:
        # Keep the live pinned widget registry from the config manager.
        # dialog.global_config can be a stale snapshot and must not overwrite
        # Config.PINNED_WIDGETS on a widget settings save.
        for key, value in dict(dialog.global_config or {}).items():
            if key == Config.PINNED_WIDGETS:
                continue
            cfg[key] = value

    pinned = cfg.get(Config.PINNED_WIDGETS, [])
    found = False
    title_toggled = False
    for i, widget in enumerate(pinned):
        if widget.get("id") != dialog.widget_id:
            continue
        found = True

        old_ranges = (widget.get("radio_ranges"), widget.get("filter_modes"))
        old_label = widget.get("label")
        widget["label"] = dialog.local_config.get("label", widget.get("label"))
        # A chart title emptied (or filled back in) changes the header layout:
        # the widget is rebuilt instead of updated in place.
        title_toggled = widget.get("type") not in ("stat_card", "text_label") and (
            bool(str(old_label or "").strip()) != bool(str(widget.get("label") or "").strip())
        )
        if "stat_key" in dialog.local_config:
            widget["stat_key"] = dialog.local_config["stat_key"]
        if "time_unit" in dialog.local_config:
            if dialog.local_config["time_unit"] in (None, "", "auto"):
                widget.pop("time_unit", None)
            else:
                widget["time_unit"] = dialog.local_config["time_unit"]
        widget["use_custom_style"] = dialog.is_unlinked

        for behavior_key in WIDGET_BEHAVIOR_KEYS:
            if behavior_key in dialog.widget_def:
                widget[behavior_key] = dialog.widget_def[behavior_key]
            elif behavior_key in ("line_opacity", "bar_gradient", "show_grid", "legend_mode", "radio_ranges", "filter_modes"):
                widget.pop(behavior_key, None)  # back to the global value

        if (widget.get("radio_ranges"), widget.get("filter_modes")) != old_ranges:
            title_toggled = True  # range buttons changed: rebuild the widget

        if dialog.is_unlinked:
            for key in PINNED_UNLINK_STYLE_KEYS:
                if key in dialog.local_config:
                    widget[key] = dialog.local_config[key]

        pinned[i] = widget
        break

    cfg[Config.PINNED_WIDGETS] = pinned
    manager.config = cfg
    manager.write_config()

    from ....widgets.pinned.main_menu.manager import MainMenuWidgetManager

    if MainMenuWidgetManager.instance_exists():
        mgr = MainMenuWidgetManager.instance()
        if hasattr(mgr, "_mark_config_dirty"):
            mgr._mark_config_dirty()
        if hasattr(mgr, "_get_config_manager"):
            mgr._get_config_manager(force_refresh=True)
        if found and title_toggled:
            try:
                old_widget = mgr._active_widgets.pop(dialog.widget_id, None)
                if old_widget is not None:
                    mgr._remove_widget_from_chart_rows(old_widget)
                    old_widget.deleteLater()
                mgr._widget_update_signatures.pop(dialog.widget_id, None)
                mgr._last_state = None
            except Exception:
                log_swallowed()
        mgr.refresh(clear_cache=False)

    mw.reset()


def _persist_dashboard_widget_settings(dialog: "WidgetSettingsDialog") -> None:
    manager = ConfigManager(mw)
    meta_cfg = dict(manager.config)
    # global_config can be an older snapshot: never let it overwrite the live pins.
    meta_cfg.update({k: v for k, v in dict(dialog.global_config or {}).items() if k != Config.PINNED_WIDGETS})

    stat_key = str(dialog.widget_def.get("stat_key") or "")
    if stat_key:
        styles_map = meta_cfg.get(Config.DASH_STAT_STYLES, {})
        if not isinstance(styles_map, dict):
            styles_map = {}
        if dialog.is_unlinked:
            local_entry = {"use_custom_style": True}
            for key in DASHBOARD_UNLINK_STYLE_KEYS:
                if key in dialog.local_config:
                    local_entry[key] = dialog.local_config[key]
            styles_map[stat_key] = local_entry
        else:
            styles_map.pop(stat_key, None)
        meta_cfg[Config.DASH_STAT_STYLES] = styles_map

    manager.config = meta_cfg
    manager.write_config()

    parent = dialog.parent()
    while parent:
        if hasattr(parent, "update_dashboard_visibility"):
            parent.update_dashboard_visibility()
            break
        parent = parent.parentWidget() if hasattr(parent, "parentWidget") else None

