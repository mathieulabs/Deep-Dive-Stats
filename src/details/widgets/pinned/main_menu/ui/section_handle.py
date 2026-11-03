# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

"""A handle to drag a whole box of pinned widgets.

While the mouse is near the left edge of a box (and there are several), a small grip
shows just left of its widgets. Dragged, it carries the whole box: the gaps between the boxes (and above /
below them all) light up as for a widget, and the box is put back where it is dropped.
The rest of the time the grip is hidden, so the screen stays as it was.
"""

from aqt.qt import (
    QApplication, QColor, QCursor, QDrag, QMimeData, QObject, QPainter, QPalette, QPixmap, QPoint,
    QPointF, QRectF, Qt, QTimer, QWidget,
)

from .....logic.logger import log_swallowed
from ......i18n import tr

MIME_SECTION = "application/x-ankidive-section"
_W, _H = 16, 26


class _Grip(QWidget):
    def __init__(self, manager, overlay):
        super().__init__(overlay)
        self._manager = manager
        self.key = None
        self._press = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip(tr("Drag to move this line"))
        self.setFixedSize(_W, _H)
        self.hide()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(self.palette().color(QPalette.ColorRole.WindowText))
        back = QColor(color)
        back.setAlpha(70 if self.underMouse() else 38)  # a light pill: seen at a glance
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(back)
        p.drawRoundedRect(QRectF(self.rect()), 5, 5)
        color.setAlpha(255 if self.underMouse() else 200)
        p.setBrush(color)
        for col in (0, 1):
            for row in (0, 1, 2):
                p.drawEllipse(QPointF(5.5 + col * 5, 7.5 + row * 5.5), 1.6, 1.6)
        p.end()

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.pos()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._press = None
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if self._press is None or not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if (event.pos() - self._press).manhattanLength() < QApplication.startDragDistance():
            return
        self._press = None
        self._drag()

    def _drag(self):
        key = self.key
        section = _section_widget(self._manager, key)
        if section is None:
            return
        from ..runtime.overlay_margins import set_drag_room
        from .drag_move import flush_pending

        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(MIME_SECTION, key.encode())
        drag.setMimeData(mime)
        try:
            pm = section.grab()
            if pm.width() > 420:
                pm = pm.scaledToWidth(420, Qt.TransformationMode.SmoothTransformation)
            faded = QPixmap(pm.size())
            faded.fill(Qt.GlobalColor.transparent)
            p = QPainter(faded)
            p.setOpacity(0.75)
            p.drawPixmap(0, 0, pm)
            p.end()
            drag.setPixmap(faded)
            drag.setHotSpot(QPoint(10, 10))
        except Exception:
            log_swallowed()
        self.hide()
        try:
            drag.exec(Qt.DropAction.MoveAction)
        finally:
            set_drag_room(False)
            flush_pending(self._manager)


def _content_rect(overlay, section):
    """Where the box's widgets are (overlay coords): its cards, not its whole width."""
    rect = None
    for w in section.findChildren(QWidget):
        if not w.isVisible():
            continue
        if w.objectName() != "pinned_widget_card" and type(w).__name__ != "StatCardWidget":
            continue
        r = w.geometry()
        r.moveTopLeft(w.mapTo(overlay, QPoint(0, 0)))
        rect = r if rect is None else rect.united(r)
    return rect


def _section_widget(manager, key):
    from .drag_layout import _sections

    for k, w, _r in _sections(manager):
        if k == key:
            return w
    return None


class _Hover(QObject):
    """Shows the grip next to the box under the mouse (checked a few times a second while
    the pinned area is shown: the boxes are made of many widgets, the mouse can be over
    any of them)."""

    def __init__(self, manager, overlay):
        super().__init__(overlay)
        self._manager = manager
        self._overlay = overlay
        self.grip = _Grip(manager, overlay)
        self._timer = QTimer(self)
        self._timer.setInterval(120)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self):
        try:
            overlay = self._overlay
            grip = self.grip
            if not overlay.isVisible() or QApplication.mouseButtons() != Qt.MouseButton.NoButton:
                return  # leave it as it is while a button is down (a drag may start)
            from .drag_layout import _sections

            sections = _sections(self._manager)
            pos = overlay.mapFromGlobal(QCursor.pos())
            if len(sections) < 2 or not overlay.rect().contains(pos) or QApplication.activePopupWidget() is not None:
                grip.hide()
                return
            for key, w, r in sections:
                content = _content_rect(overlay, w) or r
                # Only near the box's left edge (moving a whole box is rare: the grip does
                # not show up everywhere the mouse goes).
                near = content.left() - _W - 14 <= pos.x() <= content.left() + 40
                if content.top() - 4 <= pos.y() <= content.bottom() and near:
                    # Right beside what the box shows (its widgets can be centered, far
                    # from the area's edge), level with its top.
                    x = max(0, content.left() - _W - 6)
                    grip.key = key
                    moved = grip.pos() != QPoint(x, content.top() + 2) or not grip.isVisible()
                    grip.move(x, content.top() + 2)
                    grip.show()
                    grip.raise_()
                    if moved:
                        overlay.update_mask()
                    return
            if not grip.geometry().adjusted(-6, -6, 6, 6).contains(pos):
                grip.hide()
        except RuntimeError:
            pass
        except Exception:
            log_swallowed()


def install_section_handle(manager, overlay):
    if getattr(overlay, "_dd_section_hover", None) is None:
        overlay._dd_section_hover = _Hover(manager, overlay)
