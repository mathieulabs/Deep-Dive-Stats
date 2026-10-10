# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Show a chart card fullscreen and put it back where it was.

The card itself moves into the fullscreen window, so zoom, toggles and hover
carry over. A placeholder of the same size holds its slot meanwhile.
"""
from aqt.qt import (
    QDialog,
    QEvent,
    QObject,
    QTimer,
    QHBoxLayout,
    QPushButton,
    QSize,
    Qt,
    QVBoxLayout,
    QWidget,
    QWidgetItem,
)

from ..chart_utils.theme import get_theme_colors
from ...ui.theme.icons import get_svg_icon
from ....qss import set_qss
from ...logic.logger import log_swallowed

_QT_MAX = 16777215


def is_fullscreen(card):
    return bool(getattr(card, "_fullscreen_active", False))


def _alive(obj):
    if obj is None:
        return False
    try:
        obj.objectName()
        return True
    except RuntimeError:
        return False


def _find_heatmaps(card):
    """Heatmaps inside the card: they only need the height of their grid."""
    try:
        from ..charts.heatmap.widget import HeatmapWidget

        return card.findChildren(HeatmapWidget)
    except Exception:
        log_swallowed()
        return []


class _HeatmapFit(QObject):
    """Keeps a fullscreen heatmap exactly as tall as its grid, so the controls above it and
    the legend under it stay next to the grid instead of at the edges of the screen."""

    def __init__(self, heatmap):
        super().__init__(heatmap)
        self.heatmap = heatmap
        self.saved = (heatmap.minimumHeight(), heatmap.maximumHeight())
        heatmap.installEventFilter(self)
        self._pending = False
        self.schedule()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize:
            self.schedule()
        return False

    def schedule(self):
        if not self._pending:
            self._pending = True
            QTimer.singleShot(0, self.fit)

    def fit(self):
        self._pending = False
        hm = self.heatmap
        if not _alive(hm):
            return
        try:
            need = int(hm.heightForWidth(max(150, hm.width())))
        except Exception:
            log_swallowed()
            return
        if hm.minimumHeight() != need or hm.maximumHeight() != need:
            hm.setFixedHeight(need)

    def release(self):
        hm = self.heatmap
        if not _alive(hm):
            return
        try:
            hm.removeEventFilter(self)
            hm.setMaximumHeight(self.saved[1])
            hm.setMinimumHeight(self.saved[0])
        except Exception:
            log_swallowed()


def _swap_in_layout(layout, old, new):
    """Put *new* at the index of *old*. Handles the add-on's own layouts (itemList) and Qt's."""
    items = getattr(layout, "itemList", None)
    if isinstance(items, list):
        for i, item in enumerate(items):
            if item is not None and item.widget() is old:
                items[i] = QWidgetItem(new)
                layout.invalidate()
                return True
        return False
    try:
        return layout.replaceWidget(old, new) is not None
    except Exception:
        return False


class _FullscreenChartWindow(QDialog):
    def __init__(self, card, on_closed=None):
        host = card.window()
        super().__init__(host)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self._card = card
        self._on_closed = on_closed
        self._restored = False

        colors = get_theme_colors(card)
        bg = colors.get("bg")
        bg_name = bg.name() if hasattr(bg, "name") else str(bg or "#ffffff")
        is_dark = bool(colors.get("is_dark"))
        hover = "rgba(255,255,255,0.10)" if is_dark else "rgba(0,0,0,0.06)"
        self.setObjectName("deepdivestats_fullscreen")
        set_qss(self, f"QDialog#deepdivestats_fullscreen {{ background: {bg_name}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 12, 24, 24)
        root.setSpacing(8)

        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        bar.addStretch()
        close_btn = QPushButton("", self)
        close_btn.setIcon(get_svg_icon("x", size=18, context_ref=card))
        close_btn.setIconSize(QSize(18, 18))
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setToolTip("Exit fullscreen (Esc)")
        close_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        set_qss(
            close_btn,
            "QPushButton { background: transparent; border: none; border-radius: 6px; }"
            f"QPushButton:hover {{ background: {hover}; }}",
        )
        close_btn.clicked.connect(self.close)
        bar.addWidget(close_btn)
        root.addLayout(bar)

        # Take the card out of its layout, leaving a same-size placeholder.
        self._orig_parent = card.parentWidget()
        self._orig_layout = self._orig_parent.layout() if self._orig_parent is not None else None
        self._orig_min = card.minimumSize()
        self._orig_max = card.maximumSize()
        self._orig_policy = card.sizePolicy()
        self._placeholder = QWidget(self._orig_parent)
        self._placeholder.setFixedSize(card.size())
        self._placeholder.setSizePolicy(card.sizePolicy())
        for attr in ("col_span", "_col_offset"):
            if hasattr(card, attr):
                setattr(self._placeholder, attr, getattr(card, attr))
        self._placed_placeholder = bool(
            self._orig_layout is not None and _swap_in_layout(self._orig_layout, card, self._placeholder)
        )
        if self._placed_placeholder:
            self._placeholder.show()
        else:
            self._placeholder.deleteLater()
            self._placeholder = None

        card._fullscreen_active = True
        card.setParent(self)
        card.setMinimumSize(0, 0)
        card.setMaximumSize(_QT_MAX, _QT_MAX)
        self._fits = []
        heatmaps = _find_heatmaps(card)
        if heatmaps:
            # Centered, with the heatmap only as tall as its grid.
            root.addStretch(1)
            root.addWidget(card, 0)
            root.addStretch(1)
            self._fits = [_HeatmapFit(hm) for hm in heatmaps]
        else:
            root.addWidget(card, 1)
        card.show()
        card.destroyed.connect(self._on_card_destroyed)

        screen = host.screen() if host is not None else None
        if screen is not None:
            self.setGeometry(screen.geometry())

    def _on_card_destroyed(self, *_):
        self._card = None
        self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        self._restore()
        super().closeEvent(event)

    def done(self, result):
        self._restore()
        super().done(result)

    def _restore(self):
        if self._restored:
            return
        self._restored = True
        for fit in getattr(self, "_fits", []):
            fit.release()
        card = self._card if _alive(self._card) else None
        placed = False
        if card is not None:
            try:
                card.destroyed.disconnect(self._on_card_destroyed)
            except Exception:
                log_swallowed()
            self.layout().removeWidget(card)
            parent = self._orig_parent if _alive(self._orig_parent) else None
            card.setParent(parent)
            card.setMinimumSize(self._orig_min)
            card.setMaximumSize(self._orig_max)
            card.setSizePolicy(self._orig_policy)
            card._fullscreen_active = False
            if (
                parent is not None
                and self._placeholder is not None
                and _alive(self._placeholder)
                and _alive(self._orig_layout)
            ):
                placed = _swap_in_layout(self._orig_layout, self._placeholder, card)
            if placed:
                card.show()
                card.updateGeometry()
            else:
                card.hide()
        if self._placeholder is not None and _alive(self._placeholder):
            self._placeholder.hide()
            self._placeholder.deleteLater()
        if self._on_closed:
            try:
                self._on_closed(card, placed)
            except Exception:
                log_swallowed()


def open_fullscreen(card, on_closed=None):
    """Move *card* into a fullscreen window. on_closed(card, placed_back) runs on exit."""
    if card is None or is_fullscreen(card):
        return None
    win = _FullscreenChartWindow(card, on_closed=on_closed)
    win.showFullScreen()
    win.activateWindow()
    return win


def close_fullscreen(card):
    win = card.window() if card is not None else None
    if isinstance(win, _FullscreenChartWindow):
        win.close()
