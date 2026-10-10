# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .. import Config, ThemePalettes


def get_theme_palette(conf, is_dark=None):
    """Return active theme palette, or None when native preset is used."""
    preset_key = conf.get(Config.THEME_PRESET, ThemePalettes.NATIVE)
    custom_colors = conf.get(Config.THEME_CUSTOM_COLORS, {})
    is_custom = conf.get(Config.THEME_IS_CUSTOM, False)

    if preset_key == ThemePalettes.NATIVE:
        if is_dark is None:
            if is_custom and custom_colors:
                palette = ThemePalettes.ANKI_LIKE_PALETTE.copy()
                palette.update(custom_colors)
                palette.setdefault("total_line", palette.get("accent") or palette.get("text_secondary"))
                return palette
            return None
        base = (
            ThemePalettes.ANKI_LIKE_PALETTE
            if is_dark
            else ThemePalettes.ANKI_LIKE_PALETTE_LIGHT
        ).copy()
        if custom_colors:
            base.update(custom_colors)
        base.setdefault("total_line", base.get("accent") or base.get("text_secondary"))
        return base

    if preset_key in ThemePalettes.ALL:
        palette = ThemePalettes.ALL[preset_key].copy()
    else:
        custom_presets = conf.get(Config.THEME_CUSTOM_PRESETS, {}) or {}
        entry = custom_presets.get(preset_key)
        if isinstance(entry, dict):
            if isinstance(entry.get("palette"), dict):
                palette = entry["palette"].copy()
            else:
                palette = entry.copy()
        else:
            return None

    if is_custom:
        palette.update(custom_colors)

    palette.setdefault("total_line", palette.get("accent") or palette.get("text_secondary"))
    return palette
