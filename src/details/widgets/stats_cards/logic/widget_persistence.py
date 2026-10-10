# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ....ui import COLOR_DEFAULTS, Config, ThemePalettes
from ....logic.logger import log_swallowed


def _is_pinned_separate_data_color_mode(widget, conf):
    if not isinstance(conf, dict):
        return False
    if not bool(getattr(widget, "is_pinned", False)):
        return False
    stat_type = getattr(widget, "stat_type", None)
    if stat_type not in COLOR_DEFAULTS:
        return False
    use_active = bool(conf.get(Config.PINNED_USE_ACTIVE_THEME, False))
    use_separate = bool(conf.get(Config.PINNED_USE_SEPARATE_THEME, False))
    return use_active and use_separate


def _get_pinned_data_color_baseline(conf):
    preset_key = conf.get(Config.PINNED_THEME_PRESET, ThemePalettes.NATIVE)
    custom_presets = conf.get(Config.THEME_CUSTOM_PRESETS, {}) or {}
    entry = custom_presets.get(preset_key, {})
    if isinstance(entry, dict) and isinstance(entry.get("data_colors"), dict):
        return {**COLOR_DEFAULTS, **entry["data_colors"]}
    return ThemePalettes.get_preset_data_colors(preset_key)


def _build_color_updates(widget, conf, new_hex):
    stat_type = getattr(widget, "stat_type", None)
    if not stat_type:
        return {}

    if not _is_pinned_separate_data_color_mode(widget, conf):
        return {stat_type: new_hex}

    custom_map = conf.get(Config.PINNED_THEME_CUSTOM_COLORS, {})
    if not isinstance(custom_map, dict):
        custom_map = {}
    else:
        custom_map = dict(custom_map)

    baseline = _get_pinned_data_color_baseline(conf)
    baseline_hex = str(baseline.get(stat_type, COLOR_DEFAULTS.get(stat_type, "#888888"))).lower()
    if str(new_hex).lower() == baseline_hex:
        custom_map.pop(stat_type, None)
    else:
        custom_map[stat_type] = new_hex

    has_mode_override = conf.get(Config.PINNED_THEME_CUSTOM_BASE_MODE, None) is not None
    return {
        Config.PINNED_THEME_CUSTOM_COLORS: custom_map,
        Config.PINNED_THEME_IS_CUSTOM: bool(custom_map) or has_mode_override,
    }


def pick_card_color(
    widget,
    *,
    read_config_fn=None,
    write_config_fn=None,
    write_updates_fn=None,
    refresh_fn=None,
):
    from aqt.qt import QColor, QColorDialog

    current = QColor(widget.base_color)
    chosen = QColorDialog.getColor(current, widget, "Pick Stat Color")
    if not chosen.isValid():
        return

    new_hex = chosen.name()
    conf = {}
    if callable(read_config_fn):
        try:
            loaded = read_config_fn()
            if isinstance(loaded, dict):
                conf = loaded
        except Exception:
            conf = {}
    if not conf:
        fallback = getattr(widget, "addon_config", None)
        if isinstance(fallback, dict):
            conf = fallback
    if not isinstance(conf, dict):
        conf = {}

    updates = _build_color_updates(widget, conf, new_hex)
    widget.base_color = new_hex
    if updates:
        for key, value in updates.items():
            conf[key] = value
        if isinstance(getattr(widget, "addon_config", None), dict):
            for key, value in updates.items():
                widget.addon_config[key] = value
        else:
            widget.addon_config = conf

        if write_updates_fn is not None:
            write_updates_fn(updates)
        elif write_config_fn is not None:
            write_config_fn(conf)
    if refresh_fn is not None:
        refresh_fn()

    parent = widget.window()
    if hasattr(parent, "update_dashboard_visibility"):
        parent.update_dashboard_visibility()


def persist_lock_state(widget, *, read_meta_fn=None, write_config_fn=None):
    if read_meta_fn is None or write_config_fn is None:
        return
    try:
        meta = read_meta_fn()
        conf = meta.get("config", {})
        unlocked_list = conf.get("UNLOCKED_EFFECTS", [])
        card_id = widget.widget_id or widget.config_key
        if not card_id:
            return

        is_locked = widget._effect._locked
        if not is_locked and card_id not in unlocked_list:
            unlocked_list.append(card_id)
        elif is_locked and card_id in unlocked_list:
            unlocked_list.remove(card_id)

        conf["UNLOCKED_EFFECTS"] = unlocked_list
        write_config_fn(conf)
    except Exception:
        log_swallowed()
