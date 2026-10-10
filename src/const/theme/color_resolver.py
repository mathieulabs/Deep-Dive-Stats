# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .data_colors import COLOR_DEFAULTS
from .palettes import ThemePalettes


def _is_pinned_theme_context(widget_or_context=None):
    if widget_or_context is None:
        return False
    try:
        if isinstance(widget_or_context, str):
            return widget_or_context.strip().lower() == "pinned"
        raw = getattr(widget_or_context, "property", lambda _k: None)("deepdivestats_theme_context")
        if isinstance(raw, str):
            sval = raw.strip().lower()
            if sval == "pinned":
                return True
            if sval == "details":
                return False
        w = widget_or_context if hasattr(widget_or_context, "parentWidget") else None
        while w is not None:
            raw = w.property("deepdivestats_theme_context")
            if isinstance(raw, str):
                sval = raw.strip().lower()
                if sval == "pinned":
                    return True
                if sval == "details":
                    return False
            w = w.parentWidget() if hasattr(w, "parentWidget") else None
    except Exception:
        pass
    return False


def _resolve_data_colors_for_context(cfg_dict, widget_or_context=None) -> dict:
    if not isinstance(cfg_dict, dict):
        return {}
    if not _is_pinned_theme_context(widget_or_context):
        return cfg_dict
    try:
        if not bool(cfg_dict.get('Pinned_Use_Active_Theme', False)):
            return cfg_dict
        if not bool(cfg_dict.get('Pinned_Use_Separate_Theme', False)):
            return cfg_dict
        preset_key = cfg_dict.get('Pinned_Theme_Preset', ThemePalettes.NATIVE)
        custom_presets = cfg_dict.get('Theme_Custom_Presets', {}) or {}
        entry = custom_presets.get(preset_key, {})
        if isinstance(entry, dict) and isinstance(entry.get("data_colors"), dict):
            baseline = {**COLOR_DEFAULTS, **entry["data_colors"]}
        else:
            baseline = ThemePalettes.get_preset_data_colors(preset_key)
        merged = dict(cfg_dict)
        merged.update(baseline)

        # In separate pinned theme mode, manual pinned overrides are stored in
        # Pinned_Theme_Custom_Colors. Apply only data-color keys here.
        if bool(cfg_dict.get('Pinned_Theme_Is_Custom', False)):
            custom_map = cfg_dict.get('Pinned_Theme_Custom_Colors', {})
            if isinstance(custom_map, dict):
                for data_key in COLOR_DEFAULTS.keys():
                    raw_val = custom_map.get(data_key)
                    if isinstance(raw_val, str) and raw_val:
                        merged[data_key] = raw_val
        return merged
    except Exception:
        return cfg_dict


def get_color(cfg_dict: dict, color_key: str, widget_or_context=None) -> str:
    """Resolve a color from config with fallback to defaults, with optional context."""
    eff_cfg = _resolve_data_colors_for_context(cfg_dict, widget_or_context)
    fallback = COLOR_DEFAULTS.get(color_key, '#888888')
    value = eff_cfg.get(color_key, fallback)
    # A null or empty value in a hand-edited or old config would crash QColor(...) callers.
    if not isinstance(value, str) or not value.strip():
        return fallback
    return value


def get_chart_color(color_key: str, widget_or_context=None) -> str:
    """Read a chart color from addon config at call time (no cache)."""
    try:
        from ...config import read_config_dict

        cfg = read_config_dict()
        return get_color(cfg, color_key, widget_or_context)
    except Exception:
        return COLOR_DEFAULTS.get(color_key, '#888888')
