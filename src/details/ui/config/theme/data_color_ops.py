# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations

from ... import Config
from ... import COLOR_DEFAULTS, ThemePalettes
from ....logic.theme.preset_helpers import get_custom_theme_presets


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


