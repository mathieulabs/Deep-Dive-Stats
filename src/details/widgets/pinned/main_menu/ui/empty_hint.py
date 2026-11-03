# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""What the main screen shows once every widget is removed: a discreet "+ Add a widget"
card, so there is still a way back without knowing the Deep Dive window. Its "×" hides it
for good, for those who want the screen empty (Settings > Pinned Widgets brings it back).

Only when nothing at all is pinned: widgets hidden on this deck (their view setting) do
not count as empty."""

from aqt.qt import (
    QColor, QHBoxLayout, QPainter, QPen, QPushButton, QRectF, QSize, QSizePolicy, Qt, QToolButton,
    QWidget,
)

from ..imports import Config, ThemeContext, get_theme_colors
from .....logic.logger import log_swallowed
from ......qss import set_qss
from ......i18n import tr

_HIDDEN = "_dd_empty_hidden"   # the boxes taken out of the layout while the card shows
_CARD = "_dd_empty_hint"


def hint_enabled(manager):
    try:
        return bool((manager._config_manager.config or {}).get(Config.PINNED_EMPTY_HINT, True))
    except Exception:
        return True


class _EmptyCard(QWidget):
    def __init__(self, manager, parent):
        super().__init__(parent)
        self._manager = manager
        self.setObjectName("dd_empty_hint")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(64)
        t = get_theme_colors(ThemeContext.PINNED)
        dark = bool(t.get("is_dark", True))
        self._line = QColor(255, 255, 255, 60) if dark else QColor(0, 0, 0, 55)
        fg = "rgba(235,235,240,0.85)" if dark else "rgba(30,32,38,0.8)"
        hover = "rgba(255,255,255,0.07)" if dark else "rgba(0,0,0,0.05)"

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 6, 8)
        lay.addStretch(1)
        self.add_btn = QPushButton("+  " + tr("Add a widget"), self)
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        set_qss(self.add_btn,
            f"QPushButton {{ background: transparent; border: none; border-radius: 6px; color: {fg};"
            " font-size: 14px; font-weight: 600; padding: 8px 16px; }"
            f"QPushButton:hover {{ background: {hover}; }}")
        self.add_btn.clicked.connect(self._add)
        lay.addWidget(self.add_btn)
        lay.addStretch(1)
        close = QToolButton(self)
        close.setText("×")
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close.setToolTip(tr("Hide (Settings > Pinned Widgets shows it again)"))
        close.setAutoRaise(True)
        set_qss(close,
            f"QToolButton {{ background: transparent; border: none; color: {fg}; font-size: 15px; padding: 0 6px; }}"
            f"QToolButton:hover {{ background: {hover}; border-radius: 4px; }}")
        close.clicked.connect(self._dismiss)
        lay.addWidget(close, 0, Qt.AlignmentFlag.AlignTop)

    def sizeHint(self):
        return QSize(420, 64)

    def paintEvent(self, _event):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(self._line, 1.4)
            pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 10, 10)
        finally:
            p.end()

    def _add(self):
        from .add_here import open_gallery_at

        open_gallery_at(self._manager, None)

    def _dismiss(self):
        try:
            self._manager._config_manager.set_value(Config.PINNED_EMPTY_HINT, False)
        except Exception:
            log_swallowed()
        manager = self._manager
        manager._last_state = None
        manager.refresh()


def show_empty_hint(manager):
    """Show the card in place of the boxes. False when it is not wanted (the caller then
    hides the pinned area as before)."""
    overlay = getattr(manager, "_overlay", None)
    if overlay is None or not hint_enabled(manager):
        leave_empty_hint(manager)
        return False
    try:
        from ... import WidgetRegistry

        if WidgetRegistry.get_all():
            return False  # widgets, only none for this deck
        layout = manager._main_layout
        card = getattr(overlay, _CARD, None)
        hidden = getattr(overlay, _HIDDEN, None)
        if hidden is None:
            hidden = []
            setattr(overlay, _HIDDEN, hidden)
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None and w is not card:
                w.hide()
                hidden.append(w)
        if card is None:
            card = _EmptyCard(manager, overlay)
            setattr(overlay, _CARD, card)
        layout.addWidget(card)
        card.show()
        from ..rebuild.finalize import show_overlay

        show_overlay(manager, 220)
        return True
    except RuntimeError:
        return False
    except Exception:
        log_swallowed()
        return False


def leave_empty_hint(manager):
    """Back to the boxes (before a rebuild with widgets again)."""
    overlay = getattr(manager, "_overlay", None)
    if overlay is None:
        return
    try:
        card = getattr(overlay, _CARD, None)
        if card is not None:
            manager._main_layout.removeWidget(card)
            card.hide()
            card.deleteLater()
            setattr(overlay, _CARD, None)
        for w in getattr(overlay, _HIDDEN, None) or []:
            try:
                w.show()
            except RuntimeError:
                pass
        setattr(overlay, _HIDDEN, None)
    except RuntimeError:
        pass
    except Exception:
        log_swallowed()
