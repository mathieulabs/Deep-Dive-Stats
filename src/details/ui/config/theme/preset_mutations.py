# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from ... import Config, ThemePalettes

from .preset_helpers import build_custom_theme_key, clear_theme_custom_overrides


def write_custom_theme_preset(custom_presets, key, *, name, palette, base_mode, data_colors):
    custom_presets[key] = {
        "name": name,
        "palette": palette,
        "base_mode": base_mode,
        "data_colors": data_colors,
    }


def select_theme_preset(conf, preset_key):
    conf[Config.THEME_PRESET] = preset_key
    clear_theme_custom_overrides(conf)


def update_selected_custom_theme_preset(conf, current_key, custom_presets, *, palette, base_mode, data_colors):
    entry = custom_presets.get(current_key, {})
    existing_name = str(entry.get("name", current_key))
    write_custom_theme_preset(
        custom_presets,
        current_key,
        name=existing_name,
        palette=palette,
        base_mode=base_mode,
        data_colors=data_colors,
    )
    conf[Config.THEME_CUSTOM_PRESETS] = custom_presets
    clear_theme_custom_overrides(conf)


def save_new_custom_theme_preset(conf, custom_presets, *, name, palette, base_mode, data_colors):
    key = build_custom_theme_key(name, existing_custom_keys=custom_presets.keys())
    write_custom_theme_preset(
        custom_presets,
        key,
        name=name,
        palette=palette,
        base_mode=base_mode,
        data_colors=data_colors,
    )
    select_theme_preset(conf, key)
    return key


def delete_selected_custom_theme_preset(conf, custom_presets, current_key):
    if current_key in custom_presets:
        del custom_presets[current_key]
    conf[Config.THEME_CUSTOM_PRESETS] = custom_presets
    select_theme_preset(conf, ThemePalettes.NATIVE)
    if conf.get(Config.PINNED_THEME_PRESET) == current_key:
        conf[Config.PINNED_THEME_PRESET] = ThemePalettes.NATIVE

