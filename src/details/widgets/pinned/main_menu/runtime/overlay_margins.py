# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Margins around the pinned widgets overlay (left/right share one value)."""
from ..imports import Config
from .....logic.logger import log_swallowed

DEFAULT_SIDE = 20
DEFAULT_TOP = 0
DEFAULT_BOTTOM = 20
MAX_MARGIN = 200


def _clamped(conf, key, default):
    try:
        return max(0, min(MAX_MARGIN, int(conf.get(key, default))))
    except Exception:
        return default


def apply_overlay_margins(manager):
    """Set the layout margins from the settings. Returns True if they changed.

    The webview scrollbar takes room on the right of the overlay (the overlay is as wide
    as the webview), so it is added to the right margin: both sides then look equal.
    """
    layout = getattr(manager, "_main_layout", None)
    if layout is None:
        return False
    conf = manager._config_manager.config
    side = _clamped(conf, Config.PINNED_MARGIN_SIDE, DEFAULT_SIDE)
    top = _clamped(conf, Config.PINNED_MARGIN_TOP, DEFAULT_TOP)
    bottom = _clamped(conf, Config.PINNED_MARGIN_BOTTOM, DEFAULT_BOTTOM)
    scrollbar = int(getattr(manager, "_scrollbar_px", 0) or 0)
    new = (side, top, side + scrollbar, bottom)
    m = layout.contentsMargins()
    if (m.left(), m.top(), m.right(), m.bottom()) == new:
        return False
    layout.setContentsMargins(*new)
    manager._last_resize_signature = None
    return True


def measure_scrollbar(manager, web, zoom):
    """Read the width of the webview scrollbar (0 if hidden) and update the right margin."""
    if web is None:
        return

    def _done(value):
        try:
            px = max(0, min(40, int(round(float(value or 0) * zoom))))
        except Exception:
            px = 0
        if px == int(getattr(manager, "_scrollbar_px", 0) or 0):
            return
        manager._scrollbar_px = px
        try:
            if apply_overlay_margins(manager):
                manager._schedule_overlay_sync(delay_ms=0)
        except Exception:
            log_swallowed()

    try:
        web.evalWithCallback("(window.innerWidth - document.documentElement.clientWidth)", _done)
    except Exception:
        log_swallowed()


def refresh_overlay_margins():
    """Apply changed margin settings to the live overlay, if any."""
    try:
        from ..manager import MainMenuWidgetManager

        if not MainMenuWidgetManager.instance_exists():
            return
        manager = MainMenuWidgetManager.instance()
        if getattr(manager, "_overlay", None) is None:
            return
        if apply_overlay_margins(manager):
            manager._schedule_overlay_sync(delay_ms=0)
    except Exception:
        log_swallowed()
