# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .ui_helpers import (
    clear_layout,
    get_builtin_theme_defs,
    get_theme_color_keys,
)
from ....logic.theme.preset_helpers import (
    apply_theme_color_override,
    build_custom_theme_key,
    clear_theme_custom_overrides,
    get_custom_theme_presets,
    is_custom_theme_preset_selected,
    is_builtin_theme_preset_key,
    normalize_theme_base_mode,
    resolve_effective_theme_palette,
    resolve_theme_preset_base_mode,
    resolve_theme_preset_palette,
)
from .runtime_refresh import refresh_live_data_colors
from ....logic.theme.preset_mutations import (
    delete_selected_custom_theme_preset,
    save_new_custom_theme_preset,
    select_theme_preset,
    update_selected_custom_theme_preset,
    write_custom_theme_preset,
)

__all__ = [
    "get_builtin_theme_defs",
    "get_theme_color_keys",
    "clear_layout",
    "get_custom_theme_presets",
    "is_custom_theme_preset_selected",
    "clear_theme_custom_overrides",
    "build_custom_theme_key",
    "is_builtin_theme_preset_key",
    "normalize_theme_base_mode",
    "resolve_effective_theme_palette",
    "apply_theme_color_override",
    "resolve_theme_preset_base_mode",
    "resolve_theme_preset_palette",
    "refresh_live_data_colors",
    "write_custom_theme_preset",
    "select_theme_preset",
    "update_selected_custom_theme_preset",
    "save_new_custom_theme_preset",
    "delete_selected_custom_theme_preset",
]

