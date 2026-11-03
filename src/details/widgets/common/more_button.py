# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""A "⋯" button that shows up while the mouse is over a chart or a stat card and opens
its right-click menu. Many users never find the right click: this shows them the menu is
there, without adding anything to the screen when the mouse is elsewhere.

It floats over the card and takes no room, so nothing moves: on hover it goes in the
widest empty stretch of the title row, right before the row's buttons. Small stat cards get
a smaller one in their top right corner, the pinned calendar (title hidden) gets it just
left of its top controls, other cards without a title get none, and so does a row with no
room. Clicking it sends the card a context-menu event at the button, so it opens exactly
the menu a right click there would (custom menus and the contextMenuEvent() ones alike).

A Deep Dive chart also gets a pin just left of it (attach_more_button(card, pin=...)): one
click puts the chart on the main screen. It shows only when the row has room for both."""

from aqt.qt import (
    QApplication, QColor, QContextMenuEvent, QEvent, QLabel, QObject, QPainter, QPalette, QPoint,
    QPointF, QRectF, QSize, Qt, QTimer, QToolButton, QWidget,
)

from ....i18n import tr

_TITLE_NAMES = ("pinned_header", "expanded_title", "StatCardTitle")
_WIDTH = 22


def _find_title(card):
    for label in card.findChildren(QLabel):
        if label.objectName() in _TITLE_NAMES:
            return label
    return None


def draws_nothing(w):
    """An empty header box or an empty label: it holds room in the row, shows nothing."""
    if type(w) is QWidget:
        return True  # a leaf container (the Answer Buttons header has nothing in it)
    if isinstance(w, QLabel):
        pm = w.pixmap()
        return not w.text().strip() and (pm is None or pm.isNull())
    return False


def _free_spot(card, title, width, height):
    """x, y for the button in the title row: the right end of the row's rightmost empty
    stretch, right before its buttons, or None when there is no room."""
    if not title.isVisible():
        return None  # a hidden title (the pinned calendar): no row to sit in
    top_left = title.mapTo(card, QPoint(0, 0))
    band_top, band_h = top_left.y(), title.height()
    advance = min(title.width(), title.fontMetrics().horizontalAdvance(title.text()))
    align = title.alignment()
    if align & Qt.AlignmentFlag.AlignHCenter:
        text_left = top_left.x() + (title.width() - advance) // 2  # stat card titles are centred
    elif align & Qt.AlignmentFlag.AlignRight:
        text_left = top_left.x() + title.width() - advance
    else:
        text_left = top_left.x()
    title_end = text_left + advance + 4
    band_mid = band_top + band_h / 2.0
    row_left, row_right = 2, card.width() - 2
    taken = [(row_left, title_end)]
    for w in card.findChildren(QWidget):
        if w is title or not w.isVisible() or w.objectName() in ("dd_more_button", "dd_pin_button"):
            continue
        if any(isinstance(child, QWidget) and child.isVisible() for child in w.children()):
            continue  # only leaf widgets: their parents span the whole row
        if draws_nothing(w):
            continue
        pos = w.mapTo(card, QPoint(0, 0))
        if pos.y() > band_mid or pos.y() + w.height() < band_mid or w.width() >= card.width() - 20:
            continue
        taken.append((pos.x(), pos.x() + w.width()))
    taken.sort()
    best, x = None, row_left
    for start, end in taken + [(row_right, row_right)]:
        if start - x >= width + 8:
            best = start  # the rightmost gap wins: right before the buttons
        x = max(x, end)
    if best is None:
        return None
    return best - width - 4, int(band_top + (band_h - height) / 2)


def _controls_spot(card, width, height):
    """Cards whose title is hidden (the pinned calendar) but that have a row of controls
    along their top edge: the button goes just left of those controls, on their line.
    Returns (x, y, label to take the dot color from) or None."""
    row = []
    for w in card.findChildren(QWidget):
        if not w.isVisible() or w.objectName() in ("dd_more_button", "dd_pin_button"):
            continue
        if any(isinstance(child, QWidget) and child.isVisible() for child in w.children()):
            continue
        pos = w.mapTo(card, QPoint(0, 0))
        if pos.y() <= 8 and w.height() <= 32 and w.width() < card.width() // 2:
            row.append((pos.x(), pos.y(), w))
    if not row:
        return None
    left_x = min(x for x, _y, _w in row)
    top = min(y for _x, y, _w in row)
    bottom = max(y + w.height() for _x, y, w in row)
    x = left_x - width - 6
    if x < 2:
        return None
    color_from = next((w for _x, _y, w in sorted(row, key=lambda r: r[0]) if isinstance(w, QLabel)), None)
    return x, int(top + (bottom - top - height) / 2), color_from


class _MoreButton(QToolButton):
    """Three dots, drawn only while the card is hovered (the button keeps its place)."""

    def __init__(self, card, title):
        super().__init__(card)
        self._card = card
        self._title = title
        self.shown = False
        self.color_from = None  # a widget to take the dot color from instead of the title
        self.setObjectName("dd_more_button")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setToolTip(tr("Options (or right click)"))
        self.setAutoRaise(True)
        self.setStyleSheet("QToolButton { background: transparent; border: none; }")

    def _dot_color(self):
        try:
            source = self.color_from if self.color_from is not None else self._title
            color = QColor(source.palette().color(QPalette.ColorRole.WindowText))
        except RuntimeError:
            color = QColor(150, 150, 150)
        if not color.isValid():
            color = QColor(150, 150, 150)
        return color

    def paintEvent(self, _event):
        if not self.shown:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = self._dot_color()
        if self.underMouse():
            back = QColor(color)
            back.setAlpha(45)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(back)
            p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 5, 5)
            color.setAlpha(255)
        else:
            color.setAlpha(210)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        r = max(1.4, min(2.2, self.height() / 9.0))
        gap = r * 2.6
        cx, cy = self.width() / 2.0, self.height() / 2.0
        for k in (-1, 0, 1):
            p.drawEllipse(QPointF(cx + k * gap, cy), r, r)
        p.end()

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)


class _PinButton(QToolButton):
    """A pin in the title's color, drawn only while the card is hovered. After a click it
    shows a check for a moment: the chart is on the main screen."""

    SIZE = 22
    ICON = 16

    def __init__(self, card, more, on_pin):
        super().__init__(card)
        self._more = more
        self._on_pin = on_pin
        self._done = False
        self.shown = False
        self.setObjectName("dd_pin_button")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setToolTip(tr("Pin to the main screen"))
        self.setAutoRaise(True)
        self.setStyleSheet("QToolButton { background: transparent; border: none; }")
        self.setFixedSize(self.SIZE, self.SIZE)
        self.clicked.connect(self._pin)
        self.hide()

    def _pin(self):
        try:
            self._on_pin()
        except Exception:
            from ...logic.logger import log_swallowed

            log_swallowed()
            return
        self._done = True
        self.setToolTip(tr("Pinned to the main screen"))
        self.update()
        QTimer.singleShot(1600, self._reset)

    def _reset(self):
        try:
            self._done = False
            self.setToolTip(tr("Pin to the main screen"))
            self.update()
        except RuntimeError:
            pass

    def paintEvent(self, _event):
        if not self.shown:
            return
        from ...ui.theme.icons import get_svg_icon

        color = self._more._dot_color()
        color.setAlpha(255 if (self.underMouse() or self._done) else 215)
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            if self.underMouse():
                back = QColor(color)
                back.setAlpha(45)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(back)
                p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 5, 5)
            side = self.ICON
            icon = get_svg_icon("check" if self._done else "push-pin", color=color.name(), size=side)
            pm = icon.pixmap(QSize(side, side))
            p.setOpacity(color.alphaF())
            p.drawPixmap((self.width() - side) // 2, (self.height() - side) // 2, pm)
        finally:
            p.end()

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)


class _HoverFilter(QObject):
    def __init__(self, card, button, title):
        super().__init__(card)
        self.card, self.button, self.title = card, button, title
        self.pin = None
        self._pin_at = None
        self._hovered = False

    def eventFilter(self, obj, event):
        kind = event.type()
        if obj is not self.card:
            # The title row: a button showing up there (the zoom reset arrow) relays it
            # out, so move out of its way.
            if kind == QEvent.Type.LayoutRequest and self._hovered:
                QTimer.singleShot(0, self._replace)
            return False
        try:
            if kind == QEvent.Type.Enter:
                self._hovered = True
                self._replace()
            elif kind == QEvent.Type.Leave:
                self._hovered = False
                self.button.shown = False
                self.button.hide()
                self._show_pin()
            elif kind == QEvent.Type.Resize and self._hovered:
                self._replace()
        except RuntimeError:
            pass
        return False

    def _replace(self):
        try:
            if not self._hovered:
                return
            b = self.button
            if self._place():
                b.shown = True
                b.show()
                b.raise_()
                b.update()
            else:
                b.shown = False
                b.hide()
            self._show_pin()
        except RuntimeError:
            pass

    def _show_pin(self):
        """The pin where _place put it (left of "⋯", or alone when the row is short)."""
        pin = self.pin
        if pin is None:
            return
        if not self._hovered or self._pin_at is None:
            pin.shown = False
            pin.hide()
            return
        pin.move(*self._pin_at)
        pin.shown = True
        pin.show()
        pin.raise_()
        pin.update()

    def _place(self):
        """Put "⋯" (and the pin) in the title row. False when "⋯" has no room; the pin may
        still have some (it is the only way to pin with one click, "⋯" only opens the
        right-click menu)."""
        b = self.button
        b.setFixedSize(*b.normal_size)
        b.color_from = None
        self._pin_at = None
        if self.pin is not None:
            ps = self.pin.SIZE
            both = _free_spot(self.card, self.title, ps + 2 + b.width(), ps)
            if both is not None:
                self._pin_at = (both[0], both[1])
                b.move(both[0] + ps + 2, both[1] + (ps - b.height()) // 2)
                return True
            alone = _free_spot(self.card, self.title, ps, ps)
            if alone is None and not self.title.isVisible():
                found = _controls_spot(self.card, ps, ps)
                alone = found[:2] if found is not None else None
            if alone is not None:
                self._pin_at = tuple(alone)
                return False
        spot = _free_spot(self.card, self.title, b.width(), b.height())
        if spot is None:
            spot = self._corner_spot()
        if spot is None and not self.title.isVisible():
            found = _controls_spot(self.card, b.width(), b.height())
            if found is not None:
                spot, b.color_from = found[:2], found[2]
        if spot is None:
            return False
        b.move(*spot)
        return True

    def _corner_spot(self):
        """Small stat cards: no room beside the title, so a smaller button in the top
        right corner, in the card's padding above the title."""
        if self.title.objectName() != "StatCardTitle" or not self.title.isVisible():
            return None
        title_top = self.title.mapTo(self.card, QPoint(0, 0)).y()
        h = max(8, min(12, title_top - 1))
        if title_top < 6:
            return None
        self.button.setFixedSize(16, h)
        return self.card.width() - 16 - 9, max(2, title_top - h)


def attach_more_button(card, pin=None):
    """Add the hover "⋯" button to a card that has a right-click menu (once per card).
    pin: optional, called by a pin button shown next to it (Deep Dive charts)."""
    if card is None or getattr(card, "_dd_more_button", None) is not None:
        return None
    try:
        title = _find_title(card)
        if title is None:
            return None  # nowhere to put it without covering the content
        button = _MoreButton(card, title)
        height = max(14, title.sizeHint().height())
        button.normal_size = (_WIDTH, height)
        button.setFixedSize(_WIDTH, height)
        button.hide()

        def _open():
            at = button.mapTo(card, QPoint(0, button.height()))
            event = QContextMenuEvent(
                QContextMenuEvent.Reason.Mouse, at, card.mapToGlobal(at), Qt.KeyboardModifier.NoModifier
            )
            QApplication.sendEvent(card, event)

        button.clicked.connect(_open)
        hover = _HoverFilter(card, button, title)
        card.installEventFilter(hover)
        header = title.parentWidget()
        if header is not None and header is not card:
            header.installEventFilter(hover)
        if pin is not None:
            hover.pin = _PinButton(card, button, pin)
        card._dd_more_button = button
        card._dd_more_hover = hover
        return button
    except RuntimeError:
        return None
