# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

"""Drag a pinned widget onto another line or box of the same kind.

Only lines and boxes that already exist are targets, a drop never creates a new
one. Graphs stay with graphs, text boxes with text boxes, stat cards with stat
cards. While dragging, the target line is outlined and a bar shows where the
widget will land.
"""

from aqt.qt import QApplication, QColor, QFrame, QPainter, QPalette, QPen, QRectF, Qt, QTimer

from ... import WidgetRegistry
from ...drag_drop.engine import ReorderEngine
from .....logic.logger import log_swallowed

_BOX_KEY = {"stat": "stat_box", "chart": "chart_box", "text": "text_box"}
_PENDING = []


def family(widget_def):
    wtype = widget_def.get("type")
    if wtype == "stat_card":
        return "stat"
    if wtype == "text_label":
        return "text"
    return "chart"


def _nonneg(value):
    try:
        return max(0, int(value or 0))
    except Exception:
        return 0


def box_of(widget_def):
    fam = family(widget_def)
    if fam == "text":
        return _nonneg(widget_def.get("text_box", widget_def.get("chart_box", 0)))
    return _nonneg(widget_def.get(_BOX_KEY[fam], 0))


def row_of(widget_def):
    return _nonneg(widget_def.get("row_num", 0))


def find_def(widget_id):
    for d in WidgetRegistry.get_all():
        if d.get("id") == widget_id:
            return d
    return None


# marker
class _DropMarker(QFrame):
    """Outline of the target line, plus a bar where the dragged widget lands."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._bar_x = None
        self.hide()

    def show_at(self, rect, bar_x):
        self._bar_x = bar_x
        self.setGeometry(rect)
        self.show()
        self.raise_()
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QApplication.palette().color(QPalette.ColorRole.Highlight)
        fill = QColor(color)
        fill.setAlpha(34)
        painter.setPen(QPen(color, 2))
        painter.setBrush(fill)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 8, 8)
        if self._bar_x is not None:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(self._bar_x - 2, 6, 4, max(4, self.height() - 12)), 2, 2)


def show_marker(parent, rect, bar_x):
    marker = getattr(parent, "_drop_marker", None)
    if marker is None:
        marker = _DropMarker(parent)
        parent._drop_marker = marker
    marker.show_at(rect, bar_x)


def hide_marker(parent):
    marker = getattr(parent, "_drop_marker", None)
    if marker is not None:
        marker.hide()


# landing
def landing(layout, pos, exclude_id, grid):
    """(anchor widget id or None, x of the landing bar) for a drop at pos (layout coords)."""
    others = []
    for i in range(layout.count()):
        item = layout.itemAt(i)
        w = item.widget()
        if w is not None and ReorderEngine._drag_id_from_widget(w) != exclude_id:
            others.append((w, item.geometry()))
    if grid:
        idx = ReorderEngine.get_grid_target_index(layout, pos, exclude_id)
    else:
        idx = ReorderEngine.get_linear_target_index(layout, pos, exclude_id, 0)
    if not others:
        return None, layout.geometry().center().x()
    if idx < len(others):
        w, rect = others[idx]
        return ReorderEngine._drag_id_from_widget(w), rect.left() - 3
    return None, others[-1][1].right() + 3


# graphs
def chart_drag_over(manager, container, box_id, box_kind, pos, source_id):
    """Look at a drag over a graph or text box.

    Returns (status, layout, row_widget): status is "reject" (wrong kind),
    "same" (same line as the dragged widget, the live reorder handles it) or "cross".
    """
    src = find_def(source_id)
    if src is None:
        return "reject", None, None
    fam = family(src)
    if fam == "stat" or (fam == "text") != (box_kind == "text"):
        hide_marker(container)
        return "reject", None, None
    boxes = getattr(manager, "_text_boxes" if box_kind == "text" else "_chart_boxes", None) or {}
    box = boxes.get(box_id)
    rows = []
    if box:
        for idx, (row_w, ml) in enumerate(box.get("rows", [])):
            if ml.count() > 0 and row_w.isVisible():
                rows.append((idx, row_w, ml))
    if not rows:
        hide_marker(container)
        return "reject", None, None

    y = pos.y()
    idx, row_w, ml = min(
        rows,
        key=lambda r: 0 if r[1].geometry().top() <= y <= r[1].geometry().bottom() else min(
            abs(y - r[1].geometry().top()), abs(y - r[1].geometry().bottom())
        ),
    )
    manager._drag_cross = None
    if box_id == box_of(src) and idx == row_of(src):
        hide_marker(container)
        return "same", ml, row_w

    local = pos - row_w.pos()
    anchor, bar_x = landing(ml, local, source_id, grid=True)
    manager._drag_cross = {"id": source_id, "box": box_id, "row": idx, "anchor": anchor}
    show_marker(container, row_w.geometry(), bar_x + row_w.x())
    return "cross", ml, row_w


# stats
def stat_row_target(row_container):
    """(box, line) of a pinned stat row, or None for rows outside the pinned area."""
    group = row_container.parentWidget()
    box = group.property("deepdivestats_stat_box") if group is not None else None
    rows = getattr(group, "_rows", None)
    if box is None or not rows or row_container not in rows:
        return None
    return int(box), rows.index(row_container)


def stat_drag_over(container, pos, source_id):
    """Cross-line check for a drag over a pinned stat row.

    Returns True when the drag is over a different line or box than the card's own
    (the marker is shown and the drop is recorded), False when the row's own
    reorder should handle it.
    """
    target = stat_row_target(container)
    src = find_def(source_id)
    if target is None or src is None or family(src) != "stat":
        return False
    box, row = target
    if box == box_of(src) and row == row_of(src):
        hide_marker(container)
        container._drag_cross = None
        return False
    anchor, bar_x = landing(container.layout, pos, source_id, grid=False)
    container._drag_cross = {"id": source_id, "box": box, "row": row, "anchor": anchor}
    show_marker(container, container.rect(), bar_x)
    return True


# move
def queue_move(cross):
    """Remember a drop. It is applied after the drag has fully ended."""
    _PENDING[:] = [dict(cross)]


def flush_pending(manager):
    """Called once the drag loop returned: apply the queued drop, if any."""
    if not _PENDING:
        return
    cross = _PENDING.pop()
    QTimer.singleShot(0, lambda: move_to(manager, cross["id"], cross["box"], cross["row"], cross["anchor"]))


def move_to(manager, widget_id, box, row, anchor_id):
    cur = find_def(widget_id)
    if cur is None:
        return
    fam = family(cur)
    src_box, src_row = box_of(cur), row_of(cur)
    if (src_box, src_row) == (box, row):
        return
    defs = list(WidgetRegistry.get_all())

    # A line left empty closes up, the lines after it move up by one.
    left = [d for d in defs if d.get("id") != widget_id and family(d) == fam and box_of(d) == src_box]
    if not any(row_of(d) == src_row for d in left):
        for d in left:
            r = row_of(d)
            if r > src_row:
                WidgetRegistry.update_settings_bulk(d["id"], {"row_num": (r - 1) or None})
        if src_box == box and row > src_row:
            row -= 1

    box_value = int(box) if fam == "text" else (None if int(box) == 0 else int(box))
    WidgetRegistry.update_settings_bulk(
        widget_id, {_BOX_KEY[fam]: box_value, "row_num": row or None, "col_offset": None}
    )

    # Put it in the saved order right before the widget it lands in front of.
    ordered = [d["id"] for d in WidgetRegistry.get_all()]
    others = [i for i in ordered if i != widget_id]
    if anchor_id in others:
        pos = others.index(anchor_id)
    else:
        by_id = {d["id"]: d for d in WidgetRegistry.get_all()}
        mates = [
            i for i in others
            if family(by_id[i]) == fam and box_of(by_id[i]) == box and row_of(by_id[i]) == row
        ] or [i for i in others if family(by_id[i]) == fam and box_of(by_id[i]) == box]
        pos = others.index(mates[-1]) + 1 if mates else len(others)
    others.insert(pos, widget_id)
    WidgetRegistry.reorder(others)

    try:
        manager._last_state = None
        manager._last_widget_set = None
        manager.refresh(clear_cache=False)
    except Exception:
        log_swallowed()
