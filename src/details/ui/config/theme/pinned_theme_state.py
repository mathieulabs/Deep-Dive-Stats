# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations

from typing import TYPE_CHECKING

from aqt.theme import theme_manager

from ... import Config
from ... import ThemePalettes
from .preset_helpers import (
    get_custom_theme_presets,
    normalize_theme_base_mode,
    resolve_theme_preset_base_mode,
    resolve_theme_preset_palette,
)

if TYPE_CHECKING:
    from ..dialogs.tabs_config_dialog import DetailedStatsConfigDialog


def get_current_pinned_theme_base_palette(dialog: "DetailedStatsConfigDialog") -> dict:
    conf = dialog.parent_dialog.addon_config.config
    preset_key = conf.get(Config.PINNED_THEME_PRESET, ThemePalettes.NATIVE)
    return resolve_theme_preset_palette(
        preset_key=preset_key,
        custom_presets=get_custom_theme_presets(conf),
        is_night_mode=theme_manager.get_night_mode(),
    )


def get_current_pinned_theme_base_mode(dialog: "DetailedStatsConfigDialog") -> str:
    conf = dialog.parent_dialog.addon_config.config
    preset_key = conf.get(Config.PINNED_THEME_PRESET, ThemePalettes.NATIVE)
    return resolve_theme_preset_base_mode(
        preset_key=preset_key,
        custom_presets=get_custom_theme_presets(conf),
    )


def get_current_pinned_theme_effective_base_mode(dialog: "DetailedStatsConfigDialog") -> str:
    conf = dialog.parent_dialog.addon_config.config
    base_mode = get_current_pinned_theme_base_mode(dialog)
    if conf.get(Config.PINNED_THEME_IS_CUSTOM, False):
        override_raw = conf.get(Config.PINNED_THEME_CUSTOM_BASE_MODE, None)
        if override_raw is not None:
            return normalize_theme_base_mode(override_raw)
    return base_mode


def get_current_pinned_theme_effective_palette(dialog: "DetailedStatsConfigDialog") -> dict:
    conf = dialog.parent_dialog.addon_config.config
    palette = get_current_pinned_theme_base_palette(dialog)
    if conf.get(Config.PINNED_THEME_IS_CUSTOM, False):
        custom_map = conf.get(Config.PINNED_THEME_CUSTOM_COLORS, {})
        if isinstance(custom_map, dict):
            palette.update(custom_map)
    return palette


def pinned_theme_has_overrides(dialog: "DetailedStatsConfigDialog") -> bool:
    conf = dialog.parent_dialog.addon_config.config
    custom_map = conf.get(Config.PINNED_THEME_CUSTOM_COLORS, {})
    if not isinstance(custom_map, dict):
        custom_map = {}
    base_mode = get_current_pinned_theme_base_mode(dialog)
    raw_mode = conf.get(Config.PINNED_THEME_CUSTOM_BASE_MODE, None)
    has_mode_override = False
    if raw_mode is not None:
        has_mode_override = normalize_theme_base_mode(raw_mode) != base_mode
    return bool(custom_map) or has_mode_override


def set_pinned_theme_override_color(
    dialog: "DetailedStatsConfigDialog", color_key: str, new_hex: str
) -> None:
    conf = dialog.parent_dialog.addon_config.config
    custom_map = conf.get(Config.PINNED_THEME_CUSTOM_COLORS, {})
    if not isinstance(custom_map, dict):
        custom_map = {}
        conf[Config.PINNED_THEME_CUSTOM_COLORS] = custom_map

    base_hex = get_current_pinned_theme_base_palette(dialog).get(
        color_key, ThemePalettes.CHARCOAL_PALETTE.get(color_key, "#000000")
    )
    if str(new_hex).lower() == str(base_hex).lower():
        custom_map.pop(color_key, None)
    else:
        custom_map[color_key] = new_hex

    conf[Config.PINNED_THEME_IS_CUSTOM] = pinned_theme_has_overrides(dialog)
    dialog._refresh_pinned_theme_color_controls()
    dialog._apply_theme_change()


def on_pinned_theme_base_mode_changed(
    dialog: "DetailedStatsConfigDialog", selected_mode: str | None = None
) -> None:
    conf = dialog.parent_dialog.addon_config.config
    preset_key = conf.get(Config.PINNED_THEME_PRESET, ThemePalettes.NATIVE)
    if preset_key == ThemePalettes.NATIVE:
        dialog._refresh_pinned_theme_base_mode_control()
        return

    if selected_mode is None:
        selected_mode = get_current_pinned_theme_effective_base_mode(dialog)
    selected_mode = normalize_theme_base_mode(selected_mode)
    base_mode = get_current_pinned_theme_base_mode(dialog)
    conf[Config.PINNED_THEME_CUSTOM_BASE_MODE] = (
        None if selected_mode == base_mode else selected_mode
    )
    conf[Config.PINNED_THEME_IS_CUSTOM] = pinned_theme_has_overrides(dialog)
    dialog._refresh_pinned_theme_base_mode_control()
    dialog._apply_theme_change()

