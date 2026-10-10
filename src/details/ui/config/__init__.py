# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .dialogs.tabs_config_dialog import DetailedStatsConfigDialog
from .dialogs.tabs_config_dialog import find_visible_settings_dialog
from .dialogs.deck_config_dialog import DeckSettingsDialog
from .dialogs.widget_settings import WidgetSettingsDialog

__all__ = [
    "DetailedStatsConfigDialog",
    "find_visible_settings_dialog",
    "DeckSettingsDialog",
    "WidgetSettingsDialog",
]

