# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations

from ... import Config
from ... import COLOR_DEFAULTS, ThemePalettes
from .preset_helpers import get_custom_theme_presets
from .....qss import set_qss


def get_data_color_baseline(conf):
    preset_key = conf.get(Config.THEME_PRESET, ThemePalettes.NATIVE)
    custom_presets = get_custom_theme_presets(conf)
    entry = custom_presets.get(preset_key, {})
    if isinstance(entry, dict) and isinstance(entry.get("data_colors"), dict):
        return {**COLOR_DEFAULTS, **entry["data_colors"]}
    return ThemePalettes.get_preset_data_colors(preset_key)


def get_current_data_colors(conf):
    baseline = get_data_color_baseline(conf)
    return {key: conf.get(key, baseline.get(key, default)) for key, default in COLOR_DEFAULTS.items()}


def apply_data_colors(
    conf,
    data_colors,
    color_buttons,
    hex_labels,
    reset_buttons,
    update_reset_button_visibility,
):
    for key, hex_val in data_colors.items():
        conf[key] = hex_val
        ss = f"background-color: {hex_val}; border: 1px solid rgba(128,128,128,0.45); border-radius: 4px;"
        for storage_key, btn in color_buttons.items():
            if storage_key == key or storage_key.startswith(f"{key}_"):
                set_qss(btn, ss)
        for storage_key, hl in hex_labels.items():
            if storage_key == key or storage_key.startswith(f"{key}_"):
                hl.setText(hex_val.upper())
        for storage_key, btn_reset in reset_buttons.items():
            if storage_key == key or storage_key.startswith(f"{key}_"):
                update_reset_button_visibility(key, btn_reset)


def reset_colors_to_default(
    conf,
    save_global_config,
    color_buttons,
    hex_labels,
    reset_buttons,
    update_reset_button_visibility,
    write_config,
    baseline=None,
):
    if not isinstance(baseline, dict):
        baseline = get_data_color_baseline(conf)
    for key, default_hex in baseline.items():
        save_global_config(key, default_hex)
        for storage_key, btn in color_buttons.items():
            if storage_key.startswith(key):
                set_qss(btn, 
                    f"background-color: {default_hex}; border: 1px solid rgba(128,128,128,0.45); border-radius: 4px;"
                )
        for storage_key, hl in hex_labels.items():
            if storage_key.startswith(key):
                hl.setText(default_hex.upper())
        for storage_key, btn_reset in reset_buttons.items():
            if storage_key.startswith(key):
                update_reset_button_visibility(key, btn_reset)
    write_config()

