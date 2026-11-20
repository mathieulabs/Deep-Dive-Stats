# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import copy

from ... import Config
from .....i18n import N_


def get_dd_widget_setting(manager, section_key, setting_key, default=None):
    """Get a setting for a Deep Dive widget from shared config (mode-aware)."""
    suffix = "_g"
    mode_key = f"{section_key}{suffix}"

    all_settings = manager.addon_config.config.get(Config.DEEP_DIVE_WIDGET_SETTINGS, {})
    widget_settings = all_settings.get(mode_key) or {}

    return widget_settings.get(setting_key, default)


def open_dd_widget_settings(manager, section_key, widget):
    """Open widget settings dialog for a Deep Dive widget (mode-aware)."""
    from ...config import widget_settings_dialog

    type_map = {
        "activity": "activity",
        "retention": "retention",
        "added": "added",
        "distribution": "distribution",
        "card_counts": "card_counts",
        "heatmap": "heatmap",
        "hourly": "hourly",
        "future_due": "future_due",
        "review_intervals": "review_intervals",
        "stability": "stability",
        "difficulty": "difficulty",
        "retrievability": "retrievability",
    }
    w_type = type_map.get(section_key, "stat_card" if "stat" in section_key else section_key)

    label_map = {
        "activity": N_("Activity"),
        "retention": N_("Retention"),
        "heatmap": N_("Heatmap"),
        "future_due": N_("Future Due"),
        "distribution": N_("Answer Buttons"),
        "hourly": N_("Hourly Breakdown"),
        "card_counts": N_("Card Counts"),
        "review_intervals": N_("Review Intervals"),
        "stability": N_("Stability"),
        "difficulty": N_("Difficulty"),
        "retrievability": N_("Retrievability"),
        "added": N_("Added"),
    }
    from ..extra_charts import BY_TYPE as _EXTRA

    for _t, _m in _EXTRA.items():  # the charts added on demand
        label_map[_t] = _m.label

    suffix = "_g"
    mode_id = f"{section_key}{suffix}"

    widget_def = {
        "id": mode_id,
        "type": w_type,
        "label": label_map.get(section_key, section_key.replace("_", " ").title()),
        "is_grid": True,
    }

    style_key = Config.DEEP_DIVE_GRID_STYLE
    if style_key not in manager.addon_config.config:
        manager.addon_config.config[style_key] = {}
    global_style = manager.addon_config.config[style_key]

    all_settings = manager.addon_config.config.get(Config.DEEP_DIVE_WIDGET_SETTINGS, {})
    current_settings = all_settings.get(mode_id)

    local_style = copy.deepcopy(current_settings or {})
    dialog_widget_def = copy.deepcopy(widget_def)
    dialog_widget_def.update(local_style)

    current_did = None
    if isinstance(getattr(manager, "last_row_data", None), dict):
        current_did = manager.last_row_data.get("did")
    if current_did is None and isinstance(getattr(manager, "last_deck_identifier", None), int):
        current_did = manager.last_deck_identifier
    dialog_widget_def["deck_id"] = current_did
    dialog_widget_def["time_span"] = manager._get_dd_widget_setting(
        section_key, "time_span", manager.last_history_range
    )
    dialog_widget_def["custom_days"] = manager._get_dd_widget_setting(section_key, "custom_days", 7)

    dialog = widget_settings_dialog(
        dialog_widget_def,
        parent=widget,
        global_config=global_style,
        local_config=local_style,
        theme_config=manager.addon_config.config,
    )

    if dialog.exec():
        # Keep per-widget behavior toggles edited via dialog in persisted local settings.
        # (tooltip_hidden too: all its lines ticked again leaves no list, the full tooltip)
        _style_keys = ("line_opacity", "total_line", "bar_gradient", "show_grid", "legend_mode", "radio_ranges", "filter_modes", "own_colors", "tooltip_hidden")
        for key in ("show_average", "show_cumulative", "avg_on_active_days", "chart_opacity", "show_legend") + _style_keys:
            if key in dialog_widget_def:
                local_style[key] = dialog_widget_def[key]
            elif key in _style_keys:
                local_style.pop(key, None)  # back to the global value
        manager.addon_config.config[style_key] = global_style
        manager._update_dd_widget_setting(section_key, None, local_style, replace_all=True)


def update_dd_widget_setting(
    manager,
    section_key,
    key,
    value,
    replace_all=False,
    refresh=True,
    write=True,
):
    """Update one widget setting for the current mode."""
    suffix = "_g"
    mode_key = f"{section_key}{suffix}"

    conf = manager.addon_config.config
    if Config.DEEP_DIVE_WIDGET_SETTINGS not in conf:
        conf[Config.DEEP_DIVE_WIDGET_SETTINGS] = {}

    if mode_key not in conf[Config.DEEP_DIVE_WIDGET_SETTINGS]:
        gen_settings = conf[Config.DEEP_DIVE_WIDGET_SETTINGS].get(section_key, {})
        conf[Config.DEEP_DIVE_WIDGET_SETTINGS][mode_key] = copy.deepcopy(gen_settings)

    if replace_all:
        conf[Config.DEEP_DIVE_WIDGET_SETTINGS][mode_key] = value
    else:
        conf[Config.DEEP_DIVE_WIDGET_SETTINGS][mode_key][key] = value

    if write:
        manager.addon_config.write_config()
    if refresh:
        if (not replace_all) and key is not None:
            if manager._apply_dd_widget_setting_live(section_key, key, value):
                return
        manager._populate_dashboard()


