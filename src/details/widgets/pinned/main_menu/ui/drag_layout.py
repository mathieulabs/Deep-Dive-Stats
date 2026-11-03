# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

"""Drag a pinned widget between two lines or two boxes to make a new one there.

What Edit layout's buttons do, by dragging, for every kind of widget (graphs, the
calendar, texts, stat cards):
  - dropped in the gap between two lines of a box: the widget goes alone on a new
    line there;
  - dropped in the gap between two boxes, or above the first / below the last one:
    the widget goes in a new box there. That is also how a graph goes above the stat
    cards, or a stat card below the graphs.

The gaps are thin, so the target is a band around each one. While the mouse is in it
a bar with a label ("New line", "New box") shows where the widget will go. Dropping
anywhere else does what it always did (same line: reorder; another line or box:
move there).
"""

import time

from aqt.qt import QColor, QFont, QFontMetrics, QFrame, QPainter, QRect, QRectF, Qt

from ..block_order import charts_section_key, stats_section_key, texts_section_key
from ....common.row_projection import project_row_positions
from .drag_move import box_of, family, find_def, row_of
from .edit_mode import _config_manager, _defs, _refresh, _section_order, _write_updates
from ..imports import Config
from .....logic.logger import log_swallowed
from ......i18n import tr

# How far into the widgets on each side of a gap the target reaches (px). Small: a
# widget dragged by its title, along its own line, must not land in a new line or box.
# How far into a line (from its top or bottom) a drop still means a new line there.
SECTION_BAND = 10
LINE_BAND = 6
STAT_LINE_BAND = 6
# Above the first box / below the last one: this close to the edge, room opens there
# for a new box (and closes again once the drag goes back to the widgets).
EDGE_BAND = 10
_seen = [0.0]

_KEY_FN = {"stat": stats_section_key, "chart": charts_section_key, "text": texts_section_key}
_BOX_KEY = {"stat": "stat_box", "chart": "chart_box", "text": "text_box"}
_markers = []


# -- marker ---------------------------------------------------------------------------


class _GapMarker(QFrame):
    """A bar across the gap, with a small label saying what a drop there does."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._text = ""
        self.hide()

    def show_bar(self, rect, text):
        self._text = text
        f = QFont(self.font())
        f.setPixelSize(11)
        f.setBold(True)
        self.setFont(f)
        h = max(22, QFontMetrics(f).height() + 8)
        top = rect.center().y() - h // 2
        parent = self.parentWidget()
        if parent is not None:
            # Fully inside the area that shows it: at its top or bottom edge, half of the
            # label was cut off.
            top = max(0, min(top, parent.height() - h))
        self.setGeometry(rect.left(), top, rect.width(), h)
        self.show()
        self.raise_()
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        try:
            from ..imports import get_theme_colors
            accent = QColor(get_theme_colors(self).get("accent", QColor(59, 130, 246)))
        except Exception:
            accent = QColor(59, 130, 246)
        if not accent.isValid():
            accent = QColor(59, 130, 246)
        mid = self.height() / 2.0
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(accent)
        p.drawRoundedRect(QRectF(4, mid - 2, self.width() - 8, 4), 2, 2)
        if self._text:
            fm = QFontMetrics(self.font())
            tw = fm.horizontalAdvance(self._text) + 16
            pill = QRectF((self.width() - tw) / 2.0, 1, tw, self.height() - 2)
            p.drawRoundedRect(pill, pill.height() / 2.0, pill.height() / 2.0)
            p.setPen(QColor("#18181b") if accent.lightnessF() > 0.6 else QColor("#ffffff"))
            p.drawText(pill, int(Qt.AlignmentFlag.AlignCenter), self._text)
        p.end()


def show_gap(parent, rect, text):
    """Show the gap marker on parent (one marker at a time in the whole pinned area)."""
    hide_gaps(keep=parent)
    marker = getattr(parent, "_dd_gap_marker", None)
    if marker is None:
        marker = _GapMarker(parent)
        parent._dd_gap_marker = marker
        _markers.append(marker)
    marker.show_bar(rect, text)
    if hasattr(parent, "update_mask"):
        parent.update_mask()  # the pinned area shows only its widgets: let the marker in


def hide_gaps(keep=None):  # also the landing outlines
    if keep is None:
        from ..runtime.overlay_margins import set_spot_room

        set_spot_room(0)  # the room a landing outline opened under the boxes (see show_spot)
    masked = set()
    for marker in list(_markers):
        try:
            if keep is not None and marker.parent() is keep:
                continue
            if marker.isVisible() and hasattr(marker.parent(), "update_mask"):
                masked.add(marker.parent())
            marker.hide()
        except RuntimeError:
            _markers.remove(marker)
    for host in masked:
        try:
            host.update_mask()  # give the outline's room back to the page under it
        except RuntimeError:
            pass


# -- where a drop would go ------------------------------------------------------------


def _sections(manager):
    """(section key, widget, rect in overlay coords) of the boxes shown, top to bottom."""
    layout = getattr(manager, "_main_layout", None)
    out = []
    if layout is None:
        return out
    for i in range(layout.count()):
        w = layout.itemAt(i).widget()
        if w is None or not w.isVisible() or w.height() <= 0:
            continue
        key = w.property("deepdivestats_section")
        if key:
            out.append((str(key), w, w.geometry()))
    out.sort(key=lambda s: s[2].top())
    return out


def _gap_at(manager, sections, y):
    """(index among the boxes, y of the gap) when y is in a gap between two boxes, or near
    the top of the first / the bottom of the last one (the room there opens). Else None."""
    first, last = sections[0][2], sections[-1][2]
    area_h = sections[0][1].parentWidget().height()
    near_top = y <= first.top() + EDGE_BAND
    near_bottom = y >= last.bottom() - EDGE_BAND
    _seen[0] = time.monotonic()
    _set_room(near_top, near_bottom)
    if near_top:
        # Above the first box (in the room a drag opens there).
        return 0, (first.top() // 2 if first.top() >= 12 else first.top() - 4)
    if near_bottom:
        below = area_h - last.bottom()
        return len(sections), ((last.bottom() + area_h) // 2 if below >= 12 else last.bottom() + 4)
    for i in range(len(sections) - 1):
        a, b = sections[i][2], sections[i + 1][2]
        gap_y = (a.bottom() + b.top()) // 2
        if abs(y - gap_y) <= SECTION_BAND + (b.top() - a.bottom()) // 2:
            return i + 1, gap_y
    return None


def _bar(sections, line_y):
    left = min(s[2].left() for s in sections)
    right = max(s[2].right() for s in sections)
    return QRect(left, line_y - 2, right - left, 4)


def section_gap(manager, overlay_pos, source_id):
    """A drop in the gap between two boxes (or above / below them all): the cross-move
    for a new box there, with the bar to show, or None."""
    src = find_def(source_id)
    sections = _sections(manager)
    if src is None or not sections:
        return None
    hit = _gap_at(manager, sections, overlay_pos.y())
    if hit is None:
        return None
    index, line_y = hit
    fam = family(src)
    keys = [s[0] for s in sections]
    own = _KEY_FN[fam](box_of(src))
    alone = not any(
        d.get("id") != source_id and family(d) == fam and box_of(d) == box_of(src) for d in _defs()
    )
    if alone and own in keys and index in (keys.index(own), keys.index(own) + 1):
        return None  # it is that box already
    cross = {"id": source_id, "kind": "newbox", "keys": keys, "index": index}
    return cross, _bar(sections, line_y)


def block_gap(manager, overlay_pos, key):
    """A whole box dragged by its handle, over a gap between boxes: (cross, bar) or None."""
    sections = _sections(manager)
    keys = [s[0] for s in sections]
    if key not in keys:
        return None
    hit = _gap_at(manager, sections, overlay_pos.y())
    if hit is None:
        return None
    index, line_y = hit
    if index in (keys.index(key), keys.index(key) + 1):
        return None  # that is where it is
    return {"id": key, "kind": "movebox", "keys": keys, "index": index}, _bar(sections, line_y)


def move_box(manager, key, keys, index):
    """Put the box key at index among the boxes shown (keys, as they were shown)."""
    order = _section_order(manager, _defs())
    rest = [k for k in keys if k != key]
    if key in keys and keys.index(key) < index:
        index -= 1
    old_above = _above(order, key)
    order = [k for k in order if k != key]
    if index < len(rest) and rest[index] in order:
        order.insert(order.index(rest[index]), key)
    elif rest and rest[-1] in order:
        order.insert(order.index(rest[-1]) + 1, key)
    else:
        order.append(key)
    updates = {Config.PINNED_BLOCK_ORDER: order}
    updates.update(_fresh_gaps(manager, [old_above, _above(order, key), key]))
    _config_manager(manager).write_config_vals(updates)
    _refresh(manager)


def _above(order, key):
    """The box right above key in order, or None."""
    if key in order and order.index(key) > 0:
        return order[order.index(key) - 1]
    return None


def _fresh_gaps(manager, keys):
    """The settings update that puts the spaces under these boxes back to the default: a box
    put somewhere new does not take a space changed by hand for what was there before."""
    keys = {"box:" + k for k in keys if k}
    gaps = dict(_config_manager(manager).config.get(Config.PINNED_GAPS) or {})
    if not any(k in gaps for k in keys):
        return {}
    return {Config.PINNED_GAPS: {k: v for k, v in gaps.items() if k not in keys}}


def _set_room(top, bottom):
    try:
        from ..runtime.overlay_margins import set_drag_room
        set_drag_room(top, bottom)
    except Exception:
        log_swallowed()


def drag_left():
    """The drag left a part of the pinned area: if it does not come back into another part
    right away, it left the area, so close the room above / below the boxes."""
    from aqt.qt import QTimer

    def _check():
        if time.monotonic() - _seen[0] > 0.12:
            _set_room(False, False)
            hide_gaps()

    QTimer.singleShot(150, _check)


def line_gap(rows, y, source_id, box_id, fam, band=LINE_BAND):
    """A drop in the gap between two lines of a box: (row number for the new line, y of
    the gap) or None. rows: (row number, rect) of the box's lines, top to bottom."""
    src = find_def(source_id)
    if src is None or family(src) != fam or len(rows) < 2:
        return None
    for (_ra, a), (rb, b) in zip(rows, rows[1:]):
        gap_y = (a.bottom() + b.top()) // 2
        if abs(y - gap_y) <= band + (b.top() - a.bottom()) // 2:
            if box_of(src) == box_id:
                mates = [
                    d for d in _defs()
                    if d.get("id") != source_id and family(d) == fam
                    and box_of(d) == box_id and row_of(d) == row_of(src)
                ]
                if not mates and rb in (row_of(src), row_of(src) + 1):
                    return None  # already alone on a line right there
            return rb, gap_y
    return None


def inner_line_gap(manager, overlay_pos, source_id):
    """The gap between two lines seen from the pinned area itself (the gap between two
    lines of stat cards belongs to no line, so the drag lands here): (cross, bar) in
    overlay coords, or None."""
    from ..runtime.overlay_margins import row_content_rect

    y = overlay_pos.y()
    for key, w, r in _sections(manager):
        if not (r.top() <= y <= r.bottom()):
            continue
        base, _sep, num = key.partition(":")
        try:
            box = int(num or 0)
        except ValueError:
            return None
        if base == "stats":
            fam, band = "stat", STAT_LINE_BAND
            lines = [(i, row.geometry()) for i, row in enumerate(getattr(w, "_rows", []) or []) if row.isVisible()]
        else:
            fam, band = ("text" if base == "texts" else "chart"), LINE_BAND
            boxes = getattr(manager, "_text_boxes" if base == "texts" else "_chart_boxes", None) or {}
            lines = [
                (idx, row_content_rect(row_w, ml)) for idx, (row_w, ml) in enumerate((boxes.get(box) or {}).get("rows", []))
                if ml.count() > 0 and row_w.isVisible()
            ]
        lines.sort(key=lambda l: l[1].top())
        found = line_gap(lines, y - r.top(), source_id, box, fam, band=band)
        if found is None:
            return None
        new_row, gap_y = found
        left = r.left() + min(l.left() for _i, l in lines)
        right = r.left() + max(l.right() for _i, l in lines)
        cross = {"id": source_id, "kind": "newline", "box": box, "row": new_row}
        return cross, QRect(left, r.top() + gap_y - 2, right - left, 4)
    return None


def _spot_x(order, x_start, spacing, step, row_min, row_max, src_index, k, pointer_x):
    """x of the dragged widget on the line for the shift k (same rule as the line's layout)."""
    widths = [w for w, _o in order]
    offsets = [o for _w, o in order]
    offsets[src_index] = k
    base, x = [], x_start
    for w in widths:
        base.append(int(x))
        x += w + spacing
    desired = [int(b + o * step) for b, o in zip(base, offsets)]
    weights = [1.0 + 1000.0 * abs(o) for o in offsets]
    xs = project_row_positions(base_xs=base, desired_xs=desired, widths=widths, row_min=row_min,
                               row_spacing=spacing, row_max=row_max, weights=weights)
    return xs[src_index]


def _best_spot(order, src_index, x_start, spacing, step, row_min, row_max, pointer_x):
    """(shift, x) that puts the dragged widget's middle closest to the mouse: the landing
    snaps to the line's columns, like the shifts always did."""
    width = order[src_index][0]
    best = None
    for k in sorted(range(-12, 13), key=abs):
        x = _spot_x(order, x_start, spacing, step, row_min, row_max, src_index, k, pointer_x)
        d = abs(x + width / 2.0 - pointer_x)
        if best is None or d < best[0] - 0.5:
            best = (d, k, x)
    return best[1], best[2]


def _side_of(others, x):
    """"start" / "end" when x is left / right of all the other widgets of the line."""
    if not others:
        return None
    if x < min(r.left() for r in others) - 8:
        return "start"
    if x > max(r.right() for r in others) + 8:
        return "end"
    return None


def free_spot(manager, layout, row_w, local, source_id):
    """On the empty part of a line of graphs (left or right of its other widgets, with room
    there): {"side", "k", "rect"} where the widget lands, snapped to the columns. Else None."""
    widgets = []
    for i in range(layout.count()):
        w = layout.itemAt(i).widget()
        if w is not None and w.isVisible() and getattr(w, "widget_id", None) != source_id:
            widgets.append(w)
    src = (getattr(manager, "_active_widgets", None) or {}).get(source_id)
    if src is None:
        return None
    # Alone on its line: anywhere on it.
    side = _side_of([w.geometry() for w in widgets], local.x()) if widgets else "end"
    if side is None:
        return None
    spacing = max(0, layout.spacing())
    rect = layout.geometry()
    m = layout.contentsMargins()
    eff = rect.width() - m.left() - m.right()
    total = sum(w.width() for w in widgets) + src.width() + spacing * len(widgets)
    if total > eff:
        return None  # no room on this line: it would only wrap
    num_cols = max(1, (eff + spacing) // (layout.min_column_width + spacing))
    col_w = (eff - (num_cols - 1) * spacing) // num_cols
    order = [(w.width(), int(getattr(w, "_col_offset", 0) or 0)) for w in widgets]
    idx = 0 if side == "start" else len(order)
    order.insert(idx, (src.width(), 0))
    left = rect.x() + m.left()
    x_start = left + (max(0, (eff - total) // 2) if layout.centered else 0)
    k, x = _best_spot(order, idx, x_start, spacing, col_w + spacing, left, left + eff, local.x())
    return {"side": side, "k": k, "rect": QRect(int(x), rect.y() + m.top(), src.width(), max(20, src.height()))}


def free_stat_spot(container, local, source_id, source_widget):
    """Same for a line of stat cards."""
    lay = container.layout
    items = [it for it in lay._widget_items() if getattr(it.widget(), "widget_id", None) != source_id
             and getattr(it.widget(), "config_key", None) != source_id]
    if source_widget is None or not items:
        return None
    side = _side_of([it.widget().geometry() for it in items], local.x())
    if side is None:
        return None
    m_l, m_t, m_r, _m_b = lay.getContentsMargins()
    avail = container.width() - m_l - m_r
    spacing = lay._h_spacing
    widths = [lay._item_width(it) for it in items]
    src_w = source_widget.width()
    total = sum(widths) + src_w + spacing * len(widths)
    if total > avail:
        return None
    order = [(w, int(getattr(it.widget(), "_col_offset", 0) or 0)) for w, it in zip(widths, items)]
    idx = 0 if side == "start" else len(order)
    order.insert(idx, (src_w, 0))
    left = m_l
    if lay._has_leading_spacer() and lay._has_trailing_spacer():
        x_start = left + max(0, (avail - total) // 2)
    elif lay._has_leading_spacer():
        x_start = left + max(0, avail - total)
    else:
        x_start = left
    step = order[0][0] + spacing  # the line's own step: its first card's width
    k, x = _best_spot(order, idx, x_start, spacing, step, left, left + avail, local.x())
    return {"side": side, "k": k, "rect": QRect(int(x), m_t, src_w, lay._row_h)}


class _SpotMarker(QFrame):
    """Where the dragged widget will land on a line: its outline, at its exact place."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._text = ""
        self.hide()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        try:
            from ..imports import get_theme_colors
            accent = QColor(get_theme_colors(self).get("accent", QColor(59, 130, 246)))
        except Exception:
            accent = QColor(59, 130, 246)
        if not accent.isValid():
            accent = QColor(59, 130, 246)
        fill = QColor(accent)
        fill.setAlpha(45)
        from aqt.qt import QPen
        pen = QPen(accent, 2)
        pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(fill)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 10, 10)
        p.end()


def show_spot(parent, rect):
    """The outline goes on the whole pinned area, not on the line: a widget taller than the
    line's others (a chart next to the calendar) was cut at the line's bottom."""
    host = parent
    while host is not None and host.objectName() != "pinned_overlay":
        host = host.parentWidget()
    if host is None:
        host = parent
    else:
        rect = QRect(parent.mapTo(host, rect.topLeft()), rect.size())
    hide_gaps(keep=host)
    marker = getattr(host, "_dd_spot_marker", None)
    if marker is None:
        marker = _SpotMarker(host)
        host._dd_spot_marker = marker
        _markers.append(marker)
    other = getattr(host, "_dd_gap_marker", None)
    if other is not None:
        other.hide()
    marker.setGeometry(rect)
    marker.show()
    marker.raise_()
    if host.objectName() == "pinned_overlay":
        # Past the bottom of the pinned area (a tall widget on the last line): the area
        # grows under it for the time of the drag, or the outline is cut.
        from ..runtime.overlay_margins import set_spot_room, spot_room

        set_spot_room(max(0, rect.bottom() + 8 - (host.height() - spot_room())))
    if hasattr(host, "update_mask"):
        host.update_mask()  # the pinned area shows only its widgets: let the outline in


def place(manager, widget_id, box, row, side, k):
    """Put the widget at the start or the end of that line, then at its shift k there (the
    spot the outline showed)."""
    from ... import WidgetRegistry
    from .drag_move import move_to

    defs = _defs()
    cur = next((d for d in defs if d.get("id") == widget_id), None)
    if cur is None:
        return
    fam = family(cur)
    mates = [d["id"] for d in defs if d.get("id") != widget_id and family(d) == fam
             and box_of(d) == box and row_of(d) == row]
    anchor = mates[0] if (side == "start" and mates) else None
    if (box_of(cur), row_of(cur)) != (box, row):
        move_to(manager, widget_id, box, row, anchor)
    else:
        ids = [d["id"] for d in defs if d.get("id") != widget_id]
        if anchor is not None:
            ids.insert(ids.index(anchor), widget_id)
        elif mates:
            ids.insert(ids.index(mates[-1]) + 1, widget_id)
        else:
            ids.append(widget_id)
        WidgetRegistry.reorder(ids)
    _write_updates({widget_id: {"col_offset": int(k) if k else None}})
    live = (getattr(manager, "_active_widgets", None) or {}).get(widget_id)
    if live is not None:
        live._col_offset = int(k or 0)
    _refresh(manager)


# -- the moves --------------------------------------------------------------------------


def _rows_after_leaving(defs, widget_id, fam):
    """Row numbers of the family's widgets once widget_id left its line: a line left
    empty closes up. ({id: (box, row)} for the others, (box, row) it left, whether
    that line was left empty)."""
    cur = next(d for d in defs if d.get("id") == widget_id)
    sbox, srow = box_of(cur), row_of(cur)
    out = {}
    for d in defs:
        if d.get("id") == widget_id or family(d) != fam:
            continue
        out[d["id"]] = (box_of(d), row_of(d))
    left_empty = not any(b == sbox and r == srow for b, r in out.values())
    if left_empty:
        for wid, (b, r) in list(out.items()):
            if b == sbox and r > srow:
                out[wid] = (b, r - 1)
    return out, (sbox, srow), left_empty


def _box_value(fam, box):
    if fam == "text":
        return int(box)
    return None if int(box) == 0 else int(box)


def _write_rows(defs, fam, rows, widget_id, box, row):
    updates = {}
    for d in defs:
        wid = d.get("id")
        if wid in rows and rows[wid][1] != row_of(d):
            updates[wid] = {"row_num": rows[wid][1] or None}
    updates[widget_id] = {_BOX_KEY[fam]: _box_value(fam, box), "row_num": row or None, "col_offset": None}
    _write_updates(updates)


def new_line(manager, widget_id, box, row):
    """Put the widget alone on a new line at row of box (the lines from there move down)."""
    defs = _defs()
    cur = next((d for d in defs if d.get("id") == widget_id), None)
    if cur is None:
        return
    fam = family(cur)
    rows, (sbox, srow), left_empty = _rows_after_leaving(defs, widget_id, fam)
    if left_empty and sbox == box and row > srow:
        row -= 1
    for wid, (b, r) in list(rows.items()):
        if b == box and r >= row:
            rows[wid] = (b, r + 1)
    _write_rows(defs, fam, rows, widget_id, box, row)
    _refresh(manager)


def new_box(manager, widget_id, keys, index):
    """Put the widget alone in a new box, shown at index among the boxes keys."""
    defs = _defs()
    cur = next((d for d in defs if d.get("id") == widget_id), None)
    if cur is None:
        return
    fam = family(cur)
    used = [box_of(d) for d in defs if family(d) == fam]
    new_id = (max(used) + 1) if used else 1
    new_key = _KEY_FN[fam](new_id)
    order = _section_order(manager, defs)
    if index < len(keys) and keys[index] in order:
        order.insert(order.index(keys[index]), new_key)
    elif keys and keys[-1] in order:
        order.insert(order.index(keys[-1]) + 1, new_key)
    else:
        order.append(new_key)
    rows, _left, _empty = _rows_after_leaving(defs, widget_id, fam)
    updates = {Config.PINNED_BLOCK_ORDER: order}
    updates.update(_fresh_gaps(manager, [_above(order, new_key), new_key]))
    _config_manager(manager).write_config_vals(updates)
    _write_rows(defs, fam, rows, widget_id, new_id, 0)
    _refresh(manager)


def apply(manager, cross):
    """Apply a queued drop made on a gap. False when it was not one."""
    kind = cross.get("kind")
    try:
        if kind == "newline":
            new_line(manager, cross["id"], cross["box"], cross["row"])
        elif kind == "newbox":
            new_box(manager, cross["id"], cross["keys"], cross["index"])
        elif kind == "movebox":
            move_box(manager, cross["id"], cross["keys"], cross["index"])
        elif kind == "place":
            place(manager, cross["id"], cross["box"], cross["row"], cross["side"], cross.get("k", 0))
        else:
            return False
    except Exception:
        log_swallowed()
    return True


# -- the gaps between boxes (the overlay itself) -----------------------------------------


def overlay_drag(manager, overlay, event):
    """Drag events that reach the pinned area itself (a gap, or a box that does not take
    this kind of widget). True when handled."""
    from aqt.qt import QEvent
    from ...drag_drop.constants import MIME_CHART_ID, MIME_STAT_ID

    kind = event.type()
    if kind not in (QEvent.Type.DragEnter, QEvent.Type.DragMove, QEvent.Type.DragLeave, QEvent.Type.Drop):
        return False
    if kind == QEvent.Type.DragLeave:
        hide_gaps()
        manager._drag_cross = None
        drag_left()
        return False
    from .section_handle import MIME_SECTION

    mime = event.mimeData()
    fmt = next((f for f in (MIME_CHART_ID, MIME_STAT_ID, MIME_SECTION) if mime.hasFormat(f)), None)
    if fmt is None:
        return False
    source_id = mime.data(fmt).data().decode()
    if kind in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
        pos = event.position().toPoint()
        if fmt == MIME_SECTION:
            found, label = block_gap(manager, pos, source_id), tr("Move here")
        else:
            label = tr("New line")
            found = section_gap(manager, pos, source_id)
            if found is None:
                found, label = inner_line_gap(manager, pos, source_id), tr("New line")
        if found is None:
            hide_gaps()
            manager._drag_cross = None
            if kind == QEvent.Type.DragEnter:
                event.acceptProposedAction()  # keep getting the moves: a gap may come
            else:
                event.ignore()
            return True
        cross, bar = found
        manager._drag_cross = cross
        show_gap(overlay, bar, label)
        event.acceptProposedAction()
        return True
    if kind == QEvent.Type.Drop:
        hide_gaps()
        cross = getattr(manager, "_drag_cross", None)
        manager._drag_cross = None
        if cross and cross.get("id") == source_id and cross.get("kind") in ("newbox", "newline", "movebox"):
            from .drag_move import queue_move
            queue_move(cross)
            event.acceptProposedAction()
        else:
            event.ignore()
        return True
    return False


def install_overlay_drops(manager, overlay):
    """Let the pinned area itself take drops in the gaps between boxes."""
    from aqt.qt import QObject

    class _Filter(QObject):
        def eventFilter(self, obj, event):
            try:
                return overlay_drag(manager, obj, event)
            except Exception:
                log_swallowed()
                return False

    overlay.setAcceptDrops(True)
    f = _Filter(overlay)
    overlay.installEventFilter(f)
    overlay._dd_drop_filter = f
