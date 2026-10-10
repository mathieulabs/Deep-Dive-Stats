# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt import mw


def apply_standard_dialog_sizing(dialog, *, min_width: int, height_ratio: float = 0.85) -> int:
    """Apply a shared sizing policy and return computed max height."""
    screen = mw.screen()
    if not screen:
        screen = mw.app.primaryScreen()
    available_height = screen.availableGeometry().height()
    max_height = int(available_height * float(height_ratio))
    dialog.max_height = max_height
    dialog.setMaximumHeight(max_height)
    dialog.setMinimumWidth(int(min_width))
    return max_height


def clamp_dialog_height(max_height: int, total_height: int) -> int:
    return min(int(max_height), int(total_height))


def clamp_dialog_width(total_width: int, *, min_width: int, width_ratio: float = 0.8) -> int:
    screen = mw.screen()
    if not screen:
        screen = mw.app.primaryScreen()
    available_width = screen.availableGeometry().width()
    max_width = int(available_width * float(width_ratio))
    return max(int(min_width), min(int(total_width), max_width))

