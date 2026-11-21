# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Glass settings of the web pinned widgets (web_ui/pinned.py): what is behind a box blurred (frosted glass) and a
soft shadow under it. Not for the Deep Dive grid's boxes: web_preview_on() says when the settings show them."""

from __future__ import annotations

_AUTO_BLUR = 14  # px: the default blur (a saved -1, the former "Auto", is this one too: pinned.js AUTO_BLUR)


def web_preview_on(dialog=None):
    if dialog is not None and getattr(dialog, "is_grid", False):
        return False
    try:
        from .....web_ui.pinned import enabled

        return bool(enabled())
    except Exception:
        return False
