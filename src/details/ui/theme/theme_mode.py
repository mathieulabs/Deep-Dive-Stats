# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.theme import theme_manager

from .. import Config, ThemePalettes


def _normalize_theme_base_mode(mode):
    sval = str(mode).strip().lower() if mode is not None else ""
    if sval == ThemePalettes.MODE_DARK:
        return ThemePalettes.MODE_DARK
    if sval == ThemePalettes.MODE_LIGHT:
        return ThemePalettes.MODE_LIGHT
    return ThemePalettes.MODE_NATIVE


def _resolve_preset_base_mode(conf):
    preset_key = conf.get(Config.THEME_PRESET, ThemePalettes.NATIVE)
    if preset_key in ThemePalettes.PRESET_BASE_MODES:
        return ThemePalettes.PRESET_BASE_MODES[preset_key]

    custom_presets = conf.get(Config.THEME_CUSTOM_PRESETS, {}) or {}
    entry = custom_presets.get(preset_key)
    if isinstance(entry, dict):
        if "base_mode" in entry:
            return _normalize_theme_base_mode(entry.get("base_mode"))
        return ThemePalettes.MODE_DARK
    return ThemePalettes.MODE_DARK


def get_theme_base_mode(conf):
    """Return theme base mode for details: native/light/dark."""
    try:
        from ...widgets.chart_utils.theme import resolve_details_theme_mode_from_config

        return resolve_details_theme_mode_from_config(conf)
    except Exception:
        base_mode = _resolve_preset_base_mode(conf)
        if conf.get(Config.THEME_IS_CUSTOM, False):
            override_raw = conf.get(Config.THEME_CUSTOM_BASE_MODE, None)
            if override_raw is not None:
                return _normalize_theme_base_mode(override_raw)
        return base_mode


def get_theme_effective_is_dark(conf) -> bool:
    """Resolve final dark/light state for details context."""
    base_mode = get_theme_base_mode(conf)
    if base_mode == ThemePalettes.MODE_DARK:
        return True
    if base_mode == ThemePalettes.MODE_LIGHT:
        return False
    return bool(theme_manager.get_night_mode())


def is_theme_forcing_dark() -> bool:
    """Returns True only when details are explicitly forced to dark mode."""
    try:
        from ...widgets.chart_utils.theme import get_theme_manager

        return bool(get_theme_manager().is_details_force_dark())
    except Exception:
        return False
