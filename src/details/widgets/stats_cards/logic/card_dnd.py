# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import Qt

from ...pinned.drag_drop.constants import MIME_STAT_ID
from ...pinned.drag_drop.initiator import DragInitiator


def handle_mouse_press(widget, event):
    if event.button() == Qt.MouseButton.LeftButton:
        widget._drag_start_pos = event.pos()


def handle_mouse_move(widget, event):
    if not (event.buttons() & Qt.MouseButton.LeftButton):
        return False
    drag_id = widget.widget_id or widget.config_key
    if not drag_id:
        return False
    DragInitiator.maybe_start_drag(
        widget,
        event,
        getattr(widget, "_drag_start_pos", None),
        MIME_STAT_ID,
        drag_id,
    )
    return True


def handle_mouse_release(widget, event):
    if event.button() == Qt.MouseButton.LeftButton:
        if getattr(widget, "hover_effect_enabled", True):
            widget._effect.toggle_lock()
            widget._persist_lock_state()
