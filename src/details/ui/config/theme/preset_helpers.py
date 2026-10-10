# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ... import Config, ThemePalettes


def get_custom_theme_presets(conf):
    presets = conf.get(Config.THEME_CUSTOM_PRESETS, {})
    return presets if isinstance(presets, dict) else {}


def is_builtin_theme_preset_key(preset_key):
    return preset_key == ThemePalettes.NATIVE or preset_key in ThemePalettes.ALL


def is_custom_theme_preset_selected(current_key, custom_presets):
    return (not is_builtin_theme_preset_key(current_key)) and (current_key in (custom_presets or {}))


def normalize_theme_base_mode(raw_mode):
    sval = str(raw_mode).strip().lower() if raw_mode is not None else ""
    if sval == ThemePalettes.MODE_DARK:
        return ThemePalettes.MODE_DARK
    if sval == ThemePalettes.MODE_LIGHT:
        return ThemePalettes.MODE_LIGHT
    return ThemePalettes.MODE_NATIVE


def resolve_theme_preset_base_mode(preset_key, custom_presets):
    if preset_key in ThemePalettes.PRESET_BASE_MODES:
        return ThemePalettes.PRESET_BASE_MODES[preset_key]

    entry = custom_presets.get(preset_key)
    if isinstance(entry, dict):
        if "base_mode" in entry:
            return normalize_theme_base_mode(entry.get("base_mode"))
        return ThemePalettes.MODE_DARK
    return ThemePalettes.MODE_DARK


def resolve_theme_preset_palette(preset_key, custom_presets, is_night_mode):
    def _with_total_line(pal):
        if not isinstance(pal, dict):
            return ThemePalettes.CHARCOAL_PALETTE.copy()
        if "total_line" not in pal:
            pal["total_line"] = pal.get("accent") or pal.get("text_secondary") or "#3b82f6"
        return pal

    if preset_key == ThemePalettes.NATIVE:
        if is_night_mode:
            return _with_total_line(ThemePalettes.ANKI_LIKE_PALETTE.copy())
        return _with_total_line({
            "bg_root": "#ffffff",
            "bg_surface": "#f4f4f5",
            "bg_element": "#ffffff",
            "text_primary": "#18181b",
            "text_secondary": "#71717a",
            "accent": "#3b82f6",
            "accent_hover": "#2563eb",
            "border_subtle": "#e4e4e7",
            "border_strong": "#d4d4d8",
        })
    if preset_key in ThemePalettes.ALL:
        return _with_total_line(ThemePalettes.ALL[preset_key].copy())

    entry = custom_presets.get(preset_key)
    if isinstance(entry, dict):
        palette = entry.get("palette") if isinstance(entry.get("palette"), dict) else entry
        base = ThemePalettes.CHARCOAL_PALETTE.copy()
        base.update(palette)
        return _with_total_line(base)
    return _with_total_line(ThemePalettes.CHARCOAL_PALETTE.copy())


def clear_theme_custom_overrides(conf):
    conf[Config.THEME_IS_CUSTOM] = False
    conf[Config.THEME_CUSTOM_COLORS] = {}
    conf[Config.THEME_CUSTOM_BASE_MODE] = None


def build_custom_theme_key(name, existing_custom_keys):
    slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(name)).strip("_")
    if not slug:
        slug = "theme"
    key_base = f"custom_{slug}"

    reserved = set(ThemePalettes.ALL.keys()) | {ThemePalettes.NATIVE}
    existing = set(existing_custom_keys or [])
    key = key_base
    idx = 2
    while key in existing or key in reserved:
        key = f"{key_base}_{idx}"
        idx += 1
    return key


def resolve_effective_theme_palette(base_palette, conf):
    palette = dict(base_palette or {})
    if conf.get(Config.THEME_IS_CUSTOM, False):
        custom_map = conf.get(Config.THEME_CUSTOM_COLORS, {})
        if isinstance(custom_map, dict):
            palette.update(custom_map)
    return palette


def is_theme_color_overridden(color_key, custom_map, base_hex, current_hex):
    if not isinstance(custom_map, dict):
        return False
    return (color_key in custom_map) and (str(current_hex).lower() != str(base_hex).lower())


def apply_theme_color_override(custom_map, color_key, new_hex, base_hex):
    if not isinstance(custom_map, dict):
        custom_map = {}
    if str(new_hex).lower() == str(base_hex).lower():
        custom_map.pop(color_key, None)
    else:
        custom_map[color_key] = new_hex
    return custom_map

