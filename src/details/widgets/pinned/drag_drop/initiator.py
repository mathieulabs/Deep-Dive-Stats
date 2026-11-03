# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from aqt.qt import QDrag, QMimeData, QApplication, Qt

def _end_chart_drag(mime_type, accepted):
    """Reset reorder state when a drag ends, including cancelled drags, then apply a
    queued move to another line or box."""
    try:
        from .constants import MIME_CHART_ID, MIME_STAT_ID

        if mime_type not in (MIME_CHART_ID, MIME_STAT_ID):
            return
        from ..main_menu.manager import MainMenuWidgetManager

        if not MainMenuWidgetManager.instance_exists():
            return
        manager = MainMenuWidgetManager.instance()
        if mime_type == MIME_CHART_ID:
            from ..main_menu.ui.chart_drag_ops import end_chart_drag

            end_chart_drag(manager, accepted)
        from ..main_menu.ui.drag_move import flush_pending

        flush_pending(manager)
    except Exception:
        from ....logic.logger import log_swallowed

        log_swallowed()


def _is_pinned(widget):
    """True for a widget of the pinned area (not the Deep Dive window's)."""
    try:
        from ..main_menu.manager import MainMenuWidgetManager

        if not MainMenuWidgetManager.instance_exists():
            return False
        overlay = MainMenuWidgetManager.instance()._overlay
        return overlay is not None and overlay.isAncestorOf(widget)
    except Exception:
        return False


class DragInitiator:
    """
    Handles the boilerplate logic for starting a drag operation on a widget.
    """

    @staticmethod
    def maybe_start_drag(widget, event, start_pos, mime_type, widget_id):
        """
        Detects if the mouse move exceeds the drag threshold and starts QDrag if so.
        Returns True if drag started.
        """
        if start_pos is None:
            return False
        if (event.pos() - start_pos).manhattanLength() < QApplication.startDragDistance():
            return False

        drag = QDrag(widget)
        mime_data = QMimeData()

        mime_data.setData(mime_type, widget_id.encode())
        drag.setMimeData(mime_data)

        pixmap = widget.grab()
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.pos())

        pinned = _is_pinned(widget)
        if pinned:
            # The room above / below the boxes opens when the drag gets near there
            # (see drag_layout.section_gap) and always closes at the end.
            from ..main_menu.runtime.overlay_margins import set_drag_room
        try:
            result = drag.exec(Qt.DropAction.MoveAction)
        finally:
            if pinned:
                set_drag_room(False)
        _end_chart_drag(mime_type, result == Qt.DropAction.MoveAction)
        return True
