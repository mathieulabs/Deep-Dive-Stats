# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Stable shared imports for pinned main_menu modules.

This avoids repeating deep relative import chains across subpackages.
"""

from aqt import mw
from aqt.qt import QObject, QTimer, Qt, QWidget

from ....ui import Config, Period, ThemePalettes, ConfigManager, get_color
from ....logic.history_cache import GlobalHistoryCache
from ....logic import log_debug, log_info
def animate_widget_geometry(widget, target_rect, *_args, **_kwargs):
    if widget is not None and target_rect is not None:
        widget.setGeometry(target_rect)


def animations_enabled(*_args, **_kwargs):
    return False
from ...chart_utils.theme import (
    ThemeContext,
    apply_theme_context,
    get_theme_colors,
    get_theme_manager,
    sync_theme_manager_from_config,
    sync_theme_manager_and_notify,
)

__all__ = [
    "mw",
    "QObject",
    "QTimer",
    "Qt",
    "QWidget",
    "Config",
    "ThemePalettes",
    "Period",
    "get_color",
    "ConfigManager",
    "GlobalHistoryCache",
    "animate_widget_geometry",
    "animations_enabled",
    "log_info",
    "log_debug",
    "ThemeContext",
    "get_theme_manager",
    "get_theme_colors",
    "apply_theme_context",
    "sync_theme_manager_from_config",
    "sync_theme_manager_and_notify",
]
