# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The small chevron of the header buttons that open a menu (the folded range buttons "1m",
Future Due's "Breakdown"): the same thin chevron as the period and deck labels of the
pinned widgets (card_chips), drawn in the button's text color (a "▾" character changes
size and height with the font)."""

from aqt.qt import QColor, QEvent, QObject, QPainter, QPen, QPointF, QWidget, Qt

from ...logic.logger import log_swallowed

ROOM = "   "  # what the button's text ends with: the chevron is drawn over it
_HALF = 3.0      # half width of the chevron
CHEVRON_NAME = "dd_menu_chevron"


def with_room(text):
    return f"{text}{ROOM}"


class _Chevron(QWidget):
    def __init__(self, button):
        super().__init__(button)
        self._button = button
        self.setObjectName(CHEVRON_NAME)  # part of its button (more_button: not a widget of its own)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def place(self):
        b = self._button
        try:
            fm = b.fontMetrics()
            text = b.text()
            label = text[: -len(ROOM)] if text.endswith(ROOM) else text
            full_w = fm.horizontalAdvance(text)
            # The text sits in the middle of the pill's padding (the same on both sides).
            pad = max(0.0, (b.width() - full_w) / 2.0)
            x = pad + fm.horizontalAdvance(label) + fm.horizontalAdvance(" ")
            w = int(2 * _HALF + 4)
            self.setGeometry(int(round(x)), 0, w, b.height())
            self.raise_()
            self.show()
        except RuntimeError:
            pass

    def paintEvent(self, _event):
        b = self._button
        try:
            color = QColor(b.palette().color(b.foregroundRole()))
        except RuntimeError:
            return
        if not color.isValid():
            color = QColor(150, 150, 150)
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(color, 1.3)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            cx = self.width() / 2.0
            cy = self.height() / 2.0 + 0.5
            p.drawPolyline([QPointF(cx - _HALF, cy - 1.5), QPointF(cx, cy + 1.5), QPointF(cx + _HALF, cy - 1.5)])
        finally:
            p.end()


class _Follow(QObject):
    """Puts the chevron back in place when the button changes size or text."""

    def __init__(self, button, chevron):
        super().__init__(button)
        self._chevron = chevron

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.FontChange,
                            QEvent.Type.StyleChange, QEvent.Type.PaletteChange):
            self._chevron.place()
            self._chevron.update()
        elif event.type() in (QEvent.Type.Enter, QEvent.Type.Leave):
            self._chevron.update()  # its color follows the hovered text
        return False


def attach_chevron(button):
    """Give button (its text set with with_room()) the menu chevron; call place_chevron()
    after changing its text."""
    if getattr(button, "_menu_chevron", None) is not None:
        return button._menu_chevron
    try:
        chevron = _Chevron(button)
        button._menu_chevron = chevron
        button.installEventFilter(_Follow(button, chevron))
        chevron.place()
        return chevron
    except Exception:
        log_swallowed()
        return None


def place_chevron(button):
    chevron = getattr(button, "_menu_chevron", None)
    if chevron is not None:
        chevron.place()
        chevron.update()
