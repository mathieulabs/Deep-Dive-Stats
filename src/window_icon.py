# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The add-on's logo on its windows (title bar, taskbar), instead of the default icon.

Set window by window, not on the application: Anki's own windows keep their icon."""

from aqt.qt import QIcon

from .const import LOGO_PNG

_icon = None


def addon_icon(window):
    """Give one of the add-on's windows its logo."""
    global _icon
    if _icon is None:
        _icon = QIcon(LOGO_PNG)
    window.setWindowIcon(_icon)
