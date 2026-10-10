# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Keep the Details window sized for the screen it is on.

Moving it to another screen scales its size to that screen. Maximizing or going
full screen on another screen and coming back gives the same result as opening
the window from that screen.
"""
from aqt.qt import QEvent, Qt

from ...logic.logger import log_swallowed

_FULL = Qt.WindowState.WindowMaximized | Qt.WindowState.WindowFullScreen
OPEN_FRACTION = 0.85


def fit_geometry(size, pos, old_area, new_area, min_size, recenter=False):
    """Size and position (x, y, w, h) for the new screen.

    size, pos: window size and position before the move.
    old_area, new_area: (x, y, w, h) available area of each screen.
    recenter: put the window in the middle of the new screen (opened-there look).
    """
    ow, oh = max(1, old_area[2]), max(1, old_area[3])
    nx, ny, nw, nh = new_area
    w = round(size[0] * nw / ow)
    h = round(size[1] * nh / oh)
    w = max(min(min_size[0], nw), min(w, nw))
    h = max(min(min_size[1], nh), min(h, nh))
    if recenter:
        x = nx + (nw - w) // 2
        y = ny + (nh - h) // 2
    else:
        x = max(nx, min(pos[0], nx + nw - w))
        y = max(ny, min(pos[1], ny + nh - h))
    return x, y, w, h


def _area(screen):
    g = screen.availableGeometry()
    return (g.x(), g.y(), g.width(), g.height())


def _is_full(dialog):
    return bool(dialog.windowState() & _FULL)


def install(dialog):
    """Start following the window's screen. Call after the window is shown."""
    dialog._fit_screen = dialog.screen()
    if getattr(dialog, "_fit_normal_size", None) is None:
        dialog._fit_normal_size = (dialog.width(), dialog.height())
    dialog._fit_normal_screen = dialog.screen()
    handle = dialog.windowHandle()
    if handle is not None and not getattr(dialog, "_fit_connected", False):
        dialog._fit_connected = True
        handle.screenChanged.connect(lambda scr, d=dialog: _on_screen_changed(d, scr))


def on_resize(dialog):
    """Remember the normal (not maximized) size and the screen it belongs to."""
    if _is_full(dialog) or dialog.isMinimized():
        return
    dialog._fit_normal_size = (dialog.width(), dialog.height())
    dialog._fit_normal_screen = dialog.screen()


def _on_screen_changed(dialog, new_screen):
    try:
        old = getattr(dialog, "_fit_screen", None)
        dialog._fit_screen = new_screen
        if new_screen is None or old is None or old is new_screen:
            return
        if _is_full(dialog):
            # Handled when the window goes back to its normal state.
            dialog._fit_pending = True
            return
        _apply(dialog, old, new_screen, recenter=False)
    except Exception:
        log_swallowed()


def on_change(dialog, event):
    """changeEvent hook: window state changes."""
    try:
        if event.type() != QEvent.Type.WindowStateChange:
            return
        was_full = bool(event.oldState() & _FULL)
        if not was_full or _is_full(dialog) or dialog.isMinimized():
            return
        screen = dialog.screen()
        base = getattr(dialog, "_fit_normal_screen", None)
        pending = bool(getattr(dialog, "_fit_pending", False))
        dialog._fit_pending = False
        if screen is None or base is None:
            return
        if pending or screen is not base:
            _apply(dialog, base, screen, recenter=True)
    except Exception:
        log_swallowed()


def _apply(dialog, old_screen, new_screen, recenter):
    size = getattr(dialog, "_fit_normal_size", None) or (dialog.width(), dialog.height())
    min_w = min(850, _area(new_screen)[2] - 40)
    min_h = min(600, _area(new_screen)[3] - 40)
    pos = (dialog.x(), dialog.y())
    x, y, w, h = fit_geometry(size, pos, _area(old_screen), _area(new_screen), (min_w, min_h), recenter)
    dialog.setMinimumSize(min_w, min_h)
    dialog.setGeometry(x, y, w, h)
    dialog._fit_normal_screen = new_screen
    dialog._fit_normal_size = (w, h)
