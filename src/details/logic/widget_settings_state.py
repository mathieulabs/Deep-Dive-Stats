# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""A widget's settings being edited, without a window: which configs they live in and their Cancel backup.

What the Qt WidgetSettingsDialog sorted out before building its controls, kept here so that the web page
(web_ui/widget_settings.py) needs no hidden Qt dialog:
  - global_config: the shared style (the pinned config, or a Deep Dive section's style dict);
  - local_config: the widget's own settings (its definition by default);
  - addon_config: the one its controls write to (local with "Own style" on, else global);
  - theme_config: a full config for its colors (the pinned theme when opened from a pinned widget);
  - is_dashboard_context: a Deep Dive stat card (its settings are in the Deep Dive's config);
  - is_pinned_mode: the pinned config is the one edited.
The Qt dialog runs the same setup on itself (setup(self, ...)), so both read the same."""

from __future__ import annotations

import copy

from aqt import mw

from ...config import ConfigManager, set_live_config_override
from ...const import Config
from .logger import log_swallowed


def setup(obj, widget_def, parent=None, global_config=None, local_config=None, theme_config=None):
    """Fill obj (a WidgetSettingsState or the Qt dialog) with the configs of widget_def's settings."""
    obj.widget_def = widget_def
    obj.widget_id = widget_def.get("id")
    obj.type = widget_def.get("type")
    obj.global_config = global_config if global_config is not None else ConfigManager(mw).config
    # Local config defaults to the widget definition
    obj.local_config = local_config if local_config is not None else obj.widget_def
    obj.is_unlinked = obj.local_config.get("use_custom_style", False)
    obj.is_grid = widget_def.get("is_grid", False)
    obj.addon_config = obj.local_config if obj.is_unlinked else obj.global_config

    # Theme source can differ from style source (e.g. Deep Dive grid widget settings
    # stores style overrides in a compact dict). Keep a full config dict for theming.
    obj.theme_config = theme_config if isinstance(theme_config, dict) else None
    if obj.theme_config is None:
        p = parent
        while p is not None:
            cfg_obj = getattr(p, "addon_config", None)
            cfg_dict = getattr(cfg_obj, "config", None)
            if isinstance(cfg_dict, dict):
                obj.theme_config = cfg_dict
                break
            if isinstance(cfg_obj, dict):
                obj.theme_config = cfg_obj
                break
            p = p.parentWidget() if hasattr(p, "parentWidget") else None
    if obj.theme_config is None and isinstance(obj.global_config, dict):
        obj.theme_config = obj.global_config
    # Deep Dive heatmap: the chart reads the top-level config when the compact
    # grid style has no value, so show those values in the dialog too.
    if (
        obj.is_grid
        and widget_def.get("type") == "heatmap"
        and isinstance(obj.theme_config, dict)
        and obj.theme_config is not obj.global_config
        and isinstance(obj.global_config, dict)
    ):
        for _k, _v in obj.theme_config.items():
            if isinstance(_k, str) and _k.startswith("Heatmap_") and _k not in obj.global_config:
                obj.global_config[_k] = _v
    # Opened from a pinned widget: use the pinned theme, which can differ
    # from the Deep Dive one.
    if theme_config is None and isinstance(obj.theme_config, dict):
        try:
            from ..widgets.chart_utils.theme import get_context_theme_config

            obj.theme_config = get_context_theme_config(parent, obj.theme_config)
        except Exception:
            log_swallowed()

    obj.is_dashboard_context = str((widget_def or {}).get("id", "")).startswith("dashboard_")
    if hasattr(parent, "is_pinned") and not parent.is_pinned:
        obj.is_dashboard_context = True
    elif hasattr(parent, "cards"):
        try:
            cards = list(getattr(parent, "cards", []) or [])
            if cards and not any(bool(getattr(c, "is_pinned", False)) for c in cards):
                obj.is_dashboard_context = True
        except Exception:
            log_swallowed()

    # Pinned mode when global_config holds Pinned_Widgets. The dashboard context stays isolated from pinned persistence.
    obj.is_pinned_mode = ("Pinned_Widgets" in obj.global_config) and not obj.is_dashboard_context

    # Charts re-read their colours from the config while the settings are open; let them see the unsaved edits
    # (see read_config_dict).
    set_live_config_override(live_config(obj))

    obj._backup_global = copy.deepcopy(obj.global_config)
    obj._backup_local = copy.deepcopy(obj.local_config)
    obj._backup_unlinked = obj.is_unlinked


def live_config(obj):
    """The config charts read while the settings are open: the one edited. A Deep Dive
    chart's settings are a compact style dict without the colors (the charts read
    those through the Deep Dive), so they keep reading the whole config then:
    otherwise a chart rebuilt meanwhile came back in the default colors."""
    for conf in (obj.global_config, obj.theme_config):
        if isinstance(conf, dict) and (Config.PINNED_WIDGETS in conf or Config.THEME_PRESET in conf):
            return conf
    return None


def restore(obj):
    """Cancel: the configs as they were when the settings opened."""
    obj.global_config.clear()
    obj.global_config.update(obj._backup_global)
    obj.local_config.clear()
    obj.local_config.update(obj._backup_local)
    obj.is_unlinked = obj._backup_unlinked
    obj.addon_config = obj.local_config if obj.is_unlinked else obj.global_config


class WidgetSettingsState:
    """A widget's settings being edited (see the module), for the web page: no window of its own; parent is the
    widget or window they were opened from (the live preview and Save look for the widget through it)."""

    def __init__(self, widget_def, parent=None, global_config=None, local_config=None, theme_config=None):
        self._parent = parent
        setup(self, widget_def, parent, global_config, local_config, theme_config)
        try:
            from ..widgets.chart_utils.own_colors import clean_own_colors

            # (widget_colors' Cancel puts these back; the Qt dialog keeps them when it builds its Colors box)
            self._own_colors_backup = clean_own_colors(widget_def.get("own_colors"))
        except Exception:
            log_swallowed()
            self._own_colors_backup = None

    def parent(self):
        return self._parent

    def live_config(self):
        return live_config(self)

    def title(self):
        from ...i18n import tr
        from ..ui.config.widgets.label_defaults import get_default_label

        return tr("Configure Widget: {name}", name=get_default_label(self))

    def close(self):
        """The settings closed (saved or not): charts read the saved config again."""
        set_live_config_override(None)
