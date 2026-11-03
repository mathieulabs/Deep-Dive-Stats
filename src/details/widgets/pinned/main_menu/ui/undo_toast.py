# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""A short note at the mouse, in Anki's main window, after a widget was removed or the
chart labels hidden, with an Undo button. It goes away by itself (later while the mouse
is on it), and a new one replaces it: only the last change can be undone."""

from aqt import mw
from aqt.qt import QColor, QCursor, QEvent, QFrame, QHBoxLayout, QLabel, QPushButton, Qt, QTimer

from ..imports import ThemeContext, get_theme_colors
from ......qss import set_qss
from ......i18n import tr

SHOW_MS = 7000
MARGIN = 8

_current = [None]


def _profile_name():
    return getattr(getattr(mw, "pm", None), "name", None)


def _hex(color, fallback):
    try:
        c = QColor(color)
        return c.name() if c.isValid() else fallback
    except Exception:
        return fallback


class _UndoToast(QFrame):
    def __init__(self, win, text, on_undo):
        super().__init__(win)
        self._on_undo = on_undo
        self._profile = _profile_name()
        self.setObjectName("dd_undo_toast")
        t = get_theme_colors(ThemeContext.PINNED)
        dark = bool(t.get("is_dark", True))
        accent = _hex(t.get("accent"), "#3b82f6")
        fg = "#f2f2f2" if dark else "#1f2328"
        bg = "rgba(32, 33, 38, 240)" if dark else "rgba(250, 250, 252, 245)"
        border = "rgba(255, 255, 255, 45)" if dark else "rgba(0, 0, 0, 40)"
        set_qss(self,
            f"QFrame#dd_undo_toast {{ background: {bg}; border: 1px solid {border}; border-radius: 8px; }}"
            f"QLabel {{ color: {fg}; background: transparent; font-size: 13px; }}"
            f"QPushButton {{ color: {accent}; background: transparent; border: none; font-size: 13px;"
            " font-weight: 700; padding: 2px 6px; }"
            f"QPushButton:hover {{ text-decoration: underline; }}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 10, 10, 10)
        lay.setSpacing(12)
        lay.addWidget(QLabel(text))
        undo = QPushButton(tr("Undo"))
        undo.setCursor(Qt.CursorShape.PointingHandCursor)
        # No focus: when the note goes away, Qt would pass it on like a Tab press, to the
        # deck list's first "+".
        undo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        undo.clicked.connect(self._undo)
        lay.addWidget(undo)
        self.adjustSize()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.close_toast)
        self._timer.start(SHOW_MS)
        # Where the click was: the mouse is still on the menu entry just clicked.
        self._anchor = win.mapFromGlobal(QCursor.pos())
        win.installEventFilter(self)
        self._place()
        self.show()
        self.raise_()

    def _place(self):
        win = self.parentWidget()
        x = self._anchor.x() - self.width() // 2
        y = self._anchor.y() - self.height() // 2
        x = max(MARGIN, min(x, win.width() - self.width() - MARGIN))
        y = max(MARGIN, min(y, win.height() - self.height() - MARGIN))
        self.move(x, y)

    def eventFilter(self, obj, event):
        if obj is self.parentWidget() and event.type() == QEvent.Type.Resize:
            self._place()
        return False

    def enterEvent(self, event):
        self._timer.stop()  # time to read and click
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._timer.start(SHOW_MS // 2)
        super().leaveEvent(event)

    def _undo(self):
        on_undo, self._on_undo = self._on_undo, None
        self.close_toast()
        # Another profile opened meanwhile: its settings are not the ones the widget left.
        if on_undo is not None and _profile_name() == self._profile:
            on_undo()

    def close_toast(self):
        if _current[0] is self:
            _current[0] = None
        try:
            self.parentWidget().removeEventFilter(self)
            self.hide()
            self.deleteLater()
        except RuntimeError:
            pass


def show_undo_toast(text, on_undo, window=None):
    """Show the note with its Undo button (on_undo runs on click), in window (the main
    window by default; the Deep Dive window for its own cards)."""
    old = _current[0]
    if old is not None:
        old.close_toast()
    try:
        _current[0] = _UndoToast(window or mw, text, on_undo)
    except Exception:
        _current[0] = None
        from .....logic.logger import log_swallowed

        log_swallowed()
