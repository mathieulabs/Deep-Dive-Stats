# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .dialogs.widget_settings import WidgetSettingsDialog, widget_settings_dialog


def find_visible_settings_dialog():
    """Return the visible web settings window if one is open, else None."""
    try:
        from ....web_ui.settings import find_open

        return find_open()
    except Exception:
        return None


__all__ = [
    "find_visible_settings_dialog",
    "WidgetSettingsDialog",
    "widget_settings_dialog",
]
