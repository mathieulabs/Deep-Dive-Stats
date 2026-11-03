# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""A "+" to add a widget at a precise spot of the main screen.

While the mouse is near the right end of a line of widgets, a small "+" shows just after
it: the new widget goes at the end of that line. In the space between two lines it shows
there too, for a new line, and between two boxes, for a new box. A click opens the widget
gallery, as the "Add Widget..." entry of the right-click menu does.

The lines are read from the widgets on screen (their saved box and line), not from the
layouts, so stat cards, charts and texts work the same way. A widget of another kind than
the line (a stat card picked at the end of a line of charts) goes in a new box right below
it: each kind has its own boxes."""

from aqt.qt import (
    QApplication, QColor, QCursor, QPainter, QPalette, QPoint, QPointF, QRect, QRectF, Qt,
    QObject, QTimer, QWidget,
)

from .drag_move import box_of, family, row_of
from .....logic.logger import log_swallowed
from ......i18n import tr

_SIZE = 20
_END_ZONE = 70   # how far into a line, from its right end, the "+" shows up
_OUT_ZONE = 34   # and how far past it
_GAP_BAND = 5
_BOTTOM_ZONE = 24  # how far under the last line the "+" for a new line shows up


class _Plus(QWidget):
    def __init__(self, overlay, on_click):
        super().__init__(overlay)
        self._on_click = on_click
        self.target = None
        self.setObjectName("dd_add_here")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(_SIZE, _SIZE)
        self.hide()

    def paintEvent(self, _event):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            color = QColor(self.palette().color(QPalette.ColorRole.WindowText))
            back = QColor(color)
            back.setAlpha(70 if self.underMouse() else 38)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(back)
            p.drawEllipse(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5))
            color.setAlpha(255 if self.underMouse() else 200)
            pen = p.pen()
            pen.setColor(color)
            pen.setWidthF(1.8)
            pen.setStyle(Qt.PenStyle.SolidLine)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            c = QPointF(self.width() / 2.0, self.height() / 2.0)
            arm = self.width() * 0.24
            p.drawLine(QPointF(c.x() - arm, c.y()), QPointF(c.x() + arm, c.y()))
            p.drawLine(QPointF(c.x(), c.y() - arm), QPointF(c.x(), c.y() + arm))
        finally:
            p.end()

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            target = self.target
            self.hide()
            QTimer.singleShot(0, lambda t=target: self._on_click(t))
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mousePressEvent(self, event):
        event.accept()


def _lines(manager, overlay):
    """{(family, box, line): rect in overlay coords} of the lines shown, from their widgets."""
    from ... import WidgetRegistry

    defs = {d.get("id"): d for d in WidgetRegistry.get_all()}
    out = {}
    for wid, w in list((getattr(manager, "_active_widgets", None) or {}).items()):
        d = defs.get(wid)
        try:
            if d is None or w is None or not w.isVisible() or getattr(w, "_fullscreen_active", False):
                continue
            r = QRect(w.mapTo(overlay, QPoint(0, 0)), w.size())
        except RuntimeError:
            continue
        key = (family(d), box_of(d), row_of(d))
        out[key] = out[key].united(r) if key in out else r
    return out


def find_target(manager, overlay, pos):
    """(target, where the "+" goes) for the mouse at pos, or None.
    target: {"kind": "end", "family", "box", "row"}, {"kind": "newline", "family", "box",
    "row"} or {"kind": "newbox", "keys", "index"}."""
    lines = _lines(manager, overlay)
    if not lines:
        return None
    half = _SIZE // 2

    def plus_x(right):
        return min(right + 6, overlay.width() - _SIZE - 2)

    def near_end(right):
        return right - _END_ZONE <= pos.x() <= right + _OUT_ZONE

    for (fam, box, row), r in lines.items():
        if r.top() <= pos.y() <= r.bottom() and near_end(r.right()):
            target = {"kind": "end", "family": fam, "box": box, "row": row}
            return target, QPoint(plus_x(r.right()), r.center().y() - half)

    ordered = sorted(lines.items(), key=lambda kv: kv[1].top())
    for (ka, a), (kb, b) in zip(ordered, ordered[1:]):
        if not (a.bottom() - _GAP_BAND <= pos.y() <= b.top() + _GAP_BAND):
            continue
        right = max(a.right(), b.right())
        if not near_end(right):
            continue
        y = (a.bottom() + b.top()) // 2 - half
        if ka[:2] == kb[:2]:
            target = {"kind": "newline", "family": kb[0], "box": kb[1], "row": kb[2]}
            return target, QPoint(plus_x(right), y)
        from .drag_layout import _KEY_FN, _sections

        keys = [s[0] for s in _sections(manager)]
        below = _KEY_FN[kb[0]](kb[1])
        if below in keys:
            return {"kind": "newbox", "keys": keys, "index": keys.index(below)}, QPoint(plus_x(right), y)

    # Under the last line: a new line at the bottom (as between two lines).
    (fam, box, row), last = max(lines.items(), key=lambda kv: kv[1].bottom())
    if last.bottom() < pos.y() <= last.bottom() + _BOTTOM_ZONE and near_end(last.right()):
        y = min(last.bottom() + 6 - half, overlay.height() - _SIZE - 1)
        target = {"kind": "newline", "family": fam, "box": box, "row": (row or 0) + 1}
        return target, QPoint(plus_x(last.right()), y)
    return None


# -- adding ------------------------------------------------------------------------------

def _box_fields(fam, box, row=None):
    from .drag_layout import _BOX_KEY, _box_value

    fields = {_BOX_KEY[fam]: _box_value(fam, box)}
    if row is not None:
        fields["row_num"] = row or None
    return {k: v for k, v in fields.items() if v is not None}


def add_at(manager, target, choice):
    """Pin choice (an add_widget_menu.Choice) at target (see find_target; or {"kind":
    "after", "id", "family", "box", "row"} from the right-click menu), or at the end
    without one."""
    from .add_widget_menu import pin_new
    from .drag_layout import _KEY_FN, _sections, new_line
    from .edit_mode import _config_manager, _defs, _refresh, _section_order

    if choice.widget_type == "text_label" and choice.template is None:
        from aqt import mw
        from .add_widget_menu import ask_text_template

        choice.template = ask_text_template(manager, mw)
        if choice.template is None:
            return
    fam = choice.family
    defs = _defs()
    kind = (target or {}).get("kind")
    if kind in ("end", "newline", "after") and target["family"] != fam:
        # Another kind of widget than the line: a new box of its own, right below.
        keys = [s[0] for s in _sections(manager)]
        here = _KEY_FN[target["family"]](target["box"])
        index = keys.index(here) + 1 if here in keys else len(keys)
        target, kind = {"kind": "newbox", "keys": keys, "index": index}, "newbox"

    if kind == "after":
        # Right after the widget right clicked (see WidgetRegistry.add).
        pin_new(manager, choice, after_id=target["id"], refresh=False)
    elif kind == "end":
        mates = [d["id"] for d in defs if family(d) == fam and box_of(d) == target["box"] and row_of(d) == target["row"]]
        pin_new(manager, choice, after_id=mates[-1] if mates else None, refresh=False)
    elif kind == "newline":
        new_id = pin_new(manager, choice, fields=_box_fields(fam, target["box"], target["row"]), refresh=False)
        if new_id:
            new_line(manager, new_id, target["box"], target["row"])
            return
    elif kind == "newbox":
        used = [box_of(d) for d in defs if family(d) == fam]
        box = (max(used) + 1) if used else 1
        new_key = _KEY_FN[fam](box)
        keys, index = target["keys"], target["index"]
        order = _section_order(manager, defs)
        if index < len(keys) and keys[index] in order:
            order.insert(order.index(keys[index]), new_key)
        elif keys and keys[-1] in order:
            order.insert(order.index(keys[-1]) + 1, new_key)
        else:
            order.append(new_key)
        from ..imports import Config

        _config_manager(manager).write_config_vals({Config.PINNED_BLOCK_ORDER: order})
        pin_new(manager, choice, fields=_box_fields(fam, box), refresh=False)
    else:
        pin_new(manager, choice, refresh=False)
    _refresh(manager)


def open_gallery_at(manager, target):
    from .widget_gallery import open_widget_gallery

    open_widget_gallery(manager, lambda choice: add_at(manager, target, choice),
                        family=(target or {}).get("family"), where=(target or {}).get("kind"))


# -- hover --------------------------------------------------------------------------------

class _Hover(QObject):
    """Checks a few times a second where the mouse is (the lines are made of many widgets,
    the mouse can be over any of them, or in the page around them)."""

    def __init__(self, manager, overlay):
        super().__init__(overlay)
        self._manager = manager
        self._overlay = overlay
        self.plus = _Plus(overlay, lambda target: open_gallery_at(manager, target))
        self.plus.setToolTip(tr("Add a widget here"))
        self._timer = QTimer(self)
        self._timer.setInterval(120)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self):
        try:
            overlay, plus = self._overlay, self.plus
            if not overlay.isVisible() or QApplication.mouseButtons() != Qt.MouseButton.NoButton:
                return
            from ....common.guided_tour import is_running as tour_running

            pos = overlay.mapFromGlobal(QCursor.pos())
            if tour_running() or not overlay.rect().contains(pos) or QApplication.activePopupWidget() is not None \
                    or QApplication.activeModalWidget() is not None:
                self._hide()
                return
            if plus.isVisible() and plus.geometry().adjusted(-6, -6, 6, 6).contains(pos):
                return  # on its way to the "+"
            found = find_target(self._manager, overlay, pos)
            if found is None:
                self._hide()
                return
            plus.target, at = found
            moved = plus.pos() != at or not plus.isVisible()
            plus.move(at)
            plus.show()
            plus.raise_()
            if moved:
                overlay.update_mask()
        except RuntimeError:
            pass
        except Exception:
            log_swallowed()

    def _hide(self):
        if self.plus.isVisible():
            self.plus.hide()
            self._overlay.update_mask()


def install_add_here(manager, overlay):
    if getattr(overlay, "_dd_add_hover", None) is None:
        overlay._dd_add_hover = _Hover(manager, overlay)
