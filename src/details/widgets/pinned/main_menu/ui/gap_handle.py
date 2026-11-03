# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

"""Each space between two boxes, or between two lines of a box, can be made bigger or
smaller by dragging it.

While the mouse is in one of these spaces, a thin bar shows there (the cursor becomes a
double arrow). Dragged up or down, the space follows the mouse (by steps of 2 px, its size
shown beside it); a double click puts it back to its default. Each space keeps its own
size (Config.PINNED_GAPS, see overlay_margins).
"""

import time

from aqt.qt import (
    QApplication, QColor, QCursor, QLabel, QObject, QPainter, QPalette, QRect,
    QRectF, Qt, QTimer, QWidget,
)

from ..imports import Config
from .....logic.logger import log_swallowed
from ......i18n import tr
from ......qss import set_qss

_GRAB = 10  # the bar can be grabbed this high, even over a small space
_STEP = 2


def _spaces(manager, overlay):
    """(key, rect of the space in overlay coords, its default) of every space shown."""
    from .drag_layout import _sections
    from .section_handle import _content_rect
    from ..runtime.overlay_margins import (
        row_content_rect, section_gap_default,
    )

    conf = manager._config_manager.config
    sections = _sections(manager)
    out = []
    contents = {}
    for key, w, r in sections:
        contents[key] = _content_rect(overlay, w) or r
    for (ka, _wa, ra), (_kb, _wb, rb) in zip(sections, sections[1:]):
        left = min(contents[ka].left(), contents[_kb].left())
        right = max(contents[ka].right(), contents[_kb].right())
        out.append(("box:" + ka, QRect(left, ra.bottom() + 1, right - left, rb.top() - ra.bottom() - 1),
                    section_gap_default(conf)))
    for key, w, r in sections:
        base, _sep, num = key.partition(":")
        try:
            box = int(num or 0)
        except ValueError:
            continue
        content = contents[key]
        lines = []
        if base == "stats":
            for i, row in enumerate(getattr(w, "_rows", []) or []):
                if row.isVisible() and row.height() > 0:
                    g = row.geometry()
                    g.moveTopLeft(w.mapTo(overlay, g.topLeft()))
                    lines.append((i, g))
            default = section_gap_default(conf)
        else:
            boxes = getattr(manager, "_text_boxes" if base == "texts" else "_chart_boxes", None) or {}
            for i, (row_w, ml) in enumerate((boxes.get(box) or {}).get("rows", []) or []):
                if ml.count() > 0 and row_w.isVisible():
                    g = row_content_rect(row_w, ml)
                    g.moveTopLeft(row_w.parentWidget().mapTo(overlay, g.topLeft()))
                    lines.append((i, g))
            default = section_gap_default(conf)
        lines.sort(key=lambda l: l[1].top())
        for (ia, a), (_ib, b) in zip(lines, lines[1:]):
            out.append((f"line:{base}:{box}:{ia}", QRect(content.left(), a.bottom() + 1, content.width(), b.top() - a.bottom() - 1), default))
    return out


def _grab_rect(space):
    """Where the bar of a space can be grabbed: the space, at least _GRAB high."""
    if space.height() >= _GRAB:
        return QRect(space)
    c = space.top() + space.height() // 2
    return QRect(space.left(), c - _GRAB // 2, space.width(), _GRAB)


class _Bar(QWidget):
    def __init__(self, hover, overlay):
        super().__init__(overlay)
        self._hover = hover
        self.key = None
        self.default = 0
        self._start = None  # (global y, size) while dragged
        self.pill_x = 0
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setToolTip(tr("Drag to change this space (double click: back to default)"))
        self.hide()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(self.palette().color(QPalette.ColorRole.WindowText))
        p.setPen(Qt.PenStyle.NoPen)
        cy = self.height() / 2.0
        if self._start is not None:
            # Being dragged: the whole space is shown.
            color.setAlpha(110)
            p.setBrush(color)
            p.drawRoundedRect(QRectF(0, cy - 1, self.width(), 2), 1, 1)
        # Else only a small grip, where the mouse is: discreet (it is rarely used).
        color.setAlpha(140 if self._start is not None else 75)
        p.setBrush(color)
        x = max(14.0, min(self.width() - 14.0, float(self.pill_x)))
        p.drawRoundedRect(QRectF(x - 13, cy - 2.5, 26, 5), 2.5, 2.5)
        p.end()

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.key:
            self._start = (event.globalPosition().y(), self._hover.size_of(self.key, self.default))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._start is None:
            return
        y0, size0 = self._start
        size = int(round((size0 + event.globalPosition().y() - y0) / _STEP)) * _STEP
        self._hover.set_size(self.key, size, save=False)
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._start is not None:
            self._start = None
            self._hover.set_size(self.key, self._hover.size_of(self.key, self.default), save=True)
            self._hover.hide_label()
            self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.key:
            self._start = None
            self._hover.set_size(self.key, None, save=True)
            self._hover.hide_label()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class _Hover(QObject):
    """Shows the bar on the space under the mouse (checked a few times a second while the
    pinned area is shown, like the box handle)."""

    def __init__(self, manager, overlay):
        super().__init__(overlay)
        self._manager = manager
        self._overlay = overlay
        self.bar = _Bar(self, overlay)
        self._label = QLabel(overlay)
        self._label.hide()
        self._dwell = None  # (key, since): the space the mouse rests in
        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # sizes -----------------------------------------------------------------------------
    def size_of(self, key, default):
        try:
            value = (self._manager._config_manager.config.get(Config.PINNED_GAPS) or {}).get(key)
            return int(default if value is None else value)
        except Exception:
            return int(default)

    def set_size(self, key, size, save):
        """Give a space its size (None: back to its default), at once on screen."""
        from ..runtime.overlay_margins import MAX_GAP, apply_line_gaps, apply_section_gaps

        cm = self._manager._config_manager
        gaps = dict(cm.config.get(Config.PINNED_GAPS) or {})
        if size is None:
            gaps.pop(key, None)
        else:
            gaps[key] = max(0, min(MAX_GAP, int(size)))
        cm.config[Config.PINNED_GAPS] = gaps
        if save:
            try:
                cm.write_config_vals({Config.PINNED_GAPS: gaps})
            except Exception:
                log_swallowed()
        try:
            apply_section_gaps(self._manager)
            apply_line_gaps(self._manager)
            self._manager._main_layout.activate()
            self._manager.sync_overlay()
        except Exception:
            log_swallowed()
        self._place(key)
        if size is not None and not save:
            self._show_label(gaps[key])

    # the bar ---------------------------------------------------------------------------
    def _place(self, key):
        for k, space, default in _spaces(self._manager, self._overlay):
            if k == key:
                self._put(k, space, default)
                return True
        return False

    def _put(self, key, space, default):
        bar = self.bar
        rect = _grab_rect(space)
        moved = bar.geometry() != rect or not bar.isVisible()
        bar.key, bar.default = key, default
        bar.setGeometry(rect)
        bar.show()
        bar.raise_()
        if moved:
            self._overlay.update_mask()

    def _show_label(self, px):
        label = self._label
        accent = QColor(self._overlay.palette().color(QPalette.ColorRole.Highlight))
        set_qss(label, f"QLabel {{ background: {accent.name()}; color: "
                       f"{'#18181b' if accent.lightnessF() > 0.6 else '#ffffff'};"
                       " border-radius: 8px; padding: 1px 8px; font-weight: 600; font-size: 11px; }")
        label.setText(f"{int(px)} px")
        label.adjustSize()
        g = self.bar.geometry()
        # Right of the grip (where the mouse holds the space).
        x = g.left() + max(14, min(g.width() - 14, int(self.bar.pill_x))) + 22
        label.move(min(x, self._overlay.width() - label.width() - 4), g.top() + g.height() // 2 - label.height() // 2)
        label.show()
        label.raise_()
        self._overlay.update_mask()

    def hide_label(self):
        self._label.hide()
        self._overlay.update_mask()

    def _tick(self):
        try:
            overlay = self._overlay
            bar = self.bar
            if bar._start is not None:
                return  # being dragged
            if not overlay.isVisible():
                return
            if QApplication.mouseButtons() != Qt.MouseButton.NoButton:
                if bar.isVisible() and not bar.underMouse():
                    bar.hide()  # a widget is being dragged: its drop marks show instead
                    overlay.update_mask()
                return
            pos = overlay.mapFromGlobal(QCursor.pos())
            if not overlay.rect().contains(pos) or QApplication.activePopupWidget() is not None:
                if bar.isVisible():
                    bar.hide()
                    overlay.update_mask()
                return
            for key, space, default in _spaces(self._manager, overlay):
                if _grab_rect(space).contains(pos):
                    if bar.isVisible() and bar.key == key:
                        return
                    # Only once the mouse rests there a moment: passing over a space on the
                    # way somewhere shows nothing.
                    now = time.monotonic()
                    if self._dwell is None or self._dwell[0] != key:
                        self._dwell = (key, now)
                        return
                    if now - self._dwell[1] < 0.3:
                        return
                    bar.pill_x = pos.x() - _grab_rect(space).left()
                    self._put(key, space, default)
                    return
            self._dwell = None
            if bar.isVisible() and not bar.geometry().adjusted(-2, -2, 2, 2).contains(pos):
                bar.hide()
                overlay.update_mask()
        except RuntimeError:
            pass
        except Exception:
            log_swallowed()


def install_gap_handle(manager, overlay):
    if getattr(overlay, "_dd_gap_hover", None) is None:
        overlay._dd_gap_hover = _Hover(manager, overlay)
