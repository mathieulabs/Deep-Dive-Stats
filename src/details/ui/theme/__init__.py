# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .color_utils import hex_to_rgba
from .icons import get_svg_icon
from .main_dialog_qss import get_main_dialog_style
from .palette import get_theme_palette
from .runtime_apply import apply_styles
from .scrollbar_qss import get_scrollbar_style
from .settings_dialog_qss import get_settings_dialog_style
from .theme_mode import (
    get_theme_base_mode,
    get_theme_effective_is_dark,
)

__all__ = [
    "get_theme_base_mode",
    "get_theme_effective_is_dark",
    "get_theme_palette",
    "hex_to_rgba",
    "get_main_dialog_style",
    "apply_styles",
    "get_scrollbar_style",
    "get_settings_dialog_style",
    "get_svg_icon",
]
