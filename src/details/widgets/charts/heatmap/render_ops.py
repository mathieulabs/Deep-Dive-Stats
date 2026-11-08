# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..common.cache_dpr import exporting, raster_dpr
import math
from datetime import datetime, timedelta

from aqt.qt import QColor, QPainter, QPen, QRectF, Qt

from ....ui import rollover_hour
from ...chart_utils import get_theme_colors
from ...chart_utils.drawing import get_hover_marker_outline_color
from ..common.cache_keys import theme_color_token as _theme_color_token
from .metrics import entry_counts
from . import years_ops
from .....i18n import month_short, weekday_short



def _day_labels(monday_first, initials):
    """Names of the 2nd, 4th and 6th rows of the grid (Tue/Thu/Sat or Mon/Wed/Fri)."""
    days = (1, 3, 5) if monday_first else (0, 2, 4)  # date.weekday(): 0 is Monday
    names = [weekday_short(d) for d in days]
    return [name[:1].upper() for name in names] if initials else names

def _geometry_token(widget):
    """Where the grid is drawn now: a cached picture is only valid for this exact layout."""
    try:
        if years_ops.is_years(widget):
            return years_ops.geometry_token(widget)
        if getattr(widget, "view_mode", "") == "continuous":
            geo = widget._get_continuous_layout()[:7]
        else:
            geo = widget._get_grid_geometry()
        return tuple(round(float(v), 2) for v in geo)
    except Exception:
        return None


def _labels_cache_key(widget):
    theme = get_theme_colors(widget)
    return (
        _geometry_token(widget),
        int(widget.width()),
        int(widget.height()),
        str(getattr(widget, "view_mode", "")),
        bool(getattr(widget, "hide_labels", False)),
        bool(getattr(widget, "monday_first", False)),
        bool(getattr(widget, "grid_mode", False)),
        bool(getattr(widget, "show_future", False)),
        int(round(float(getattr(widget, "scale", 1.0)) * 1000.0)),
        int(getattr(widget, "cont_month_offset", 0)),
        str(getattr(widget, "end_date", "")),
        _theme_color_token(theme.get("text")),
        str(widget.font().family()),
    )


def _scaffold_cache_key(widget):
    return (
        _labels_cache_key(widget),
        _theme_color_token(widget.empty_color),
        int(round(float(getattr(widget, "rounding", 0.0)) * 1000.0)),
    )


def _same_rect(a, b):
    return (
        abs(float(a.x()) - float(b.x())) < 0.001
        and abs(float(a.y()) - float(b.y())) < 0.001
        and abs(float(a.width()) - float(b.width())) < 0.001
        and abs(float(a.height()) - float(b.height())) < 0.001
    )


def _premul(color):
    a = float(color.alpha())
    return (a, float(color.red()) * a, float(color.green()) * a, float(color.blue()) * a)


def _mix(p1, p2, t):
    """Colour between two premultiplied colours (same result as the widget's _lerp_color)."""
    a = p1[0] + (p2[0] - p1[0]) * t
    if a <= 0.001:
        return QColor(0, 0, 0, 0)
    r = (p1[1] + (p2[1] - p1[1]) * t) / a
    g = (p1[2] + (p2[2] - p1[2]) * t) / a
    b = (p1[3] + (p2[3] - p1[3]) * t) / a
    return QColor(
        max(0, min(255, int(round(r)))),
        max(0, min(255, int(round(g)))),
        max(0, min(255, int(round(b)))),
        max(0, min(255, int(round(a)))),
    )


def _prepared_pairs(widget, pairs, include_empty_pairs):
    """What each cell pair draws, worked out once per transition: the pairs do not
    change while it runs, only the progress does."""
    rounding = float(getattr(widget, "rounding", 0.0)) / 100.0
    key = (len(pairs), bool(include_empty_pairs), rounding, int(QColor(widget.empty_color).rgba()))
    cached = getattr(widget, "_prepared_cell_pairs", None)
    if cached is not None and cached[1] is pairs and cached[0] == key:
        return cached[2]
    out = []
    for old_item, new_item in pairs:
        if old_item and new_item:
            old_rect, old_col = old_item
            new_rect, new_col = new_item
            old_empty = widget._is_empty_cell_color(old_col)
            new_empty = widget._is_empty_cell_color(new_col)
            if old_empty and new_empty and not include_empty_pairs:
                continue
            if old_empty and not new_empty and not include_empty_pairs:
                kind = "in"  # fades in over the scaffold
            elif new_empty and not old_empty and not include_empty_pairs:
                # The scaffold already draws the empty cell under this one, so fade the old
                # cell out over it. Blending towards the empty colour drew it twice and left
                # a darker cell that jumped lighter when the fade ended.
                kind = "out"
            else:
                kind = "mix"
            out.append((
                kind,
                old_rect,
                (old_rect.x(), old_rect.y(), old_rect.width(), old_rect.height()),
                (new_rect.x(), new_rect.y(), new_rect.width(), new_rect.height()),
                (old_rect.width() / 2.0) * rounding,
                (new_rect.width() / 2.0) * rounding,
                QColor(old_col),
                QColor(new_col),
                _premul(old_col),
                _premul(new_col),
                _same_rect(old_rect, new_rect),
                int(QColor(old_col).rgba()) == int(QColor(new_col).rgba()),
            ))
        elif old_item:
            old_rect, old_col = old_item
            if widget._is_empty_cell_color(old_col) and not include_empty_pairs:
                continue
            out.append(("old", old_rect, None, None, (old_rect.width() / 2.0) * rounding, 0.0, QColor(old_col), None, None, None, True, True))
        elif new_item:
            new_rect, new_col = new_item
            if widget._is_empty_cell_color(new_col) and not include_empty_pairs:
                continue
            out.append(("new", new_rect, None, None, (new_rect.width() / 2.0) * rounding, 0.0, QColor(new_col), None, None, None, True, True))
    widget._prepared_cell_pairs = (key, pairs, out)
    return out


_MAX_GROUPS = 12


def _fade_pictures(widget, painter, prepared):
    """The transition as a few pictures instead of a thousand cells drawn one by one (7 ms
    a frame, measured): the cells are grouped by how they move (most stay; when a year is
    added or removed, whole blocks shift by the same offset). Each group is drawn once with
    its old colours and once with its new ones; a frame mixes the two and slides the
    group. The same picture as drawing every cell. None when the cells change size or move
    in too many different ways (drawn cell by cell)."""
    from aqt.qt import QPixmap

    try:
        tr = painter.worldTransform()
        if tr.isRotating() or abs(tr.m11() - tr.m22()) > 1e-6:
            return None
        dev = painter.device()
        dpr = float(dev.devicePixelRatioF()) if hasattr(dev, "devicePixelRatioF") else 1.0
        scale = dpr * abs(tr.m11())
    except Exception:
        return None
    key = (id(prepared), round(scale, 4))
    cached = getattr(widget, "_fade_pictures", None)
    if cached is not None and cached[0] == key and cached[1] is prepared:
        return cached[2]
    result = None
    groups = {}
    ok = bool(prepared)
    for item in prepared:
        kind = item[0]
        if kind in ("mix", "in", "out") and not item[10]:
            # The cell's move as a scale and shift (another deck: another cell size and
            # place); the cells of one block share it.
            o, n = item[2], item[3]
            if o[2] <= 0 or o[3] <= 0:
                ok = False
                break
            sx, sy = n[2] / o[2], n[3] / o[3]
            move = (round(sx, 3), round(sy, 3), round(n[0] - sx * o[0], 1), round(n[1] - sy * o[1], 1))
        else:
            move = (1.0, 1.0, 0.0, 0.0)
        groups.setdefault(move, []).append(item)
        if len(groups) > _MAX_GROUPS:
            ok = False
            break
    if ok and groups:
        result = []

        def _pixel_box(r):
            """r grown to whole screen pixels: (logical rect, width px, height px)."""
            x0 = math.floor((r.x() - 1) * tr.m11() * dpr + tr.dx() * dpr)
            y0 = math.floor((r.y() - 1) * tr.m22() * dpr + tr.dy() * dpr)
            x1 = math.ceil((r.right() + 1) * tr.m11() * dpr + tr.dx() * dpr)
            y1 = math.ceil((r.bottom() + 1) * tr.m22() * dpr + tr.dy() * dpr)
            bx = (x0 / dpr - tr.dx()) / tr.m11()
            by = (y0 / dpr - tr.dy()) / tr.m22()
            return QRectF(bx, by, (x1 - x0) / scale, (y1 - y0) / scale), int(x1 - x0), int(y1 - y0)

        for move, items in groups.items():
            bounds = None
            end = None  # where the group's cells end: their new rects (exact, not the rounded move)
            for item in items:
                bounds = QRectF(item[1]) if bounds is None else bounds.united(item[1])
                n = item[3] if (item[0] in ("mix", "in", "out") and not item[10]) else None
                r_new = QRectF(n[0], n[1], n[2], n[3]) if n is not None else QRectF(item[1])
                end = r_new if end is None else end.united(r_new)
            if bounds is None or bounds.width() <= 0 or bounds.height() <= 0 or end.width() <= 0 or end.height() <= 0:
                continue
            # The group's scale and shift, from its cells' old and new extents (exact).
            sx = end.width() / bounds.width()
            sy = end.height() / bounds.height()
            tx = end.x() - sx * bounds.x()
            ty = end.y() - sy * bounds.y()
            # Each picture on whole screen pixels where it is shown as is: the old one at the
            # start, the new one at the end, drawn at the new places and size. Both ends land
            # pixel for pixel on the cells drawn one by one (a single picture scaled to the
            # new size came out a hair soft and the cells sharpened when the fade ended).
            box_old, pw_o, ph_o = _pixel_box(bounds)
            box_new, pw_n, ph_n = _pixel_box(end)
            if pw_o * ph_o > 16_000_000 or pw_n * ph_n > 16_000_000:
                result = None
                break
            pics = []
            for side, box, pw, ph in (("old", box_old, pw_o, ph_o), ("new", box_new, pw_n, ph_n)):
                pm = QPixmap(pw, ph)
                pm.fill(Qt.GlobalColor.transparent)
                q = QPainter(pm)
                q.setRenderHint(QPainter.RenderHint.Antialiasing)
                q.setPen(Qt.PenStyle.NoPen)
                q.scale(scale, scale)
                q.translate(-box.x(), -box.y())
                for kind, rect0, _o, n, r_old, r_new, c_old, c_new, _p1, _p2, same_rect, *_rest in items:
                    if side == "old":
                        if kind not in ("mix", "out", "old"):
                            continue
                        q.setBrush(c_old)
                        q.drawRoundedRect(rect0, r_old, r_old)
                        continue
                    if kind in ("mix", "in"):
                        q.setBrush(c_new)
                    elif kind == "new":
                        q.setBrush(c_old)  # a cell only in the new data keeps its colour in c_old
                    else:
                        continue
                    if kind in ("mix", "in") and not same_rect:
                        q.drawRoundedRect(QRectF(n[0], n[1], n[2], n[3]), r_new, r_new)
                    else:
                        q.drawRoundedRect(rect0, r_old, r_old)
                q.end()
                pics.append(pm)
            result.append((box_old, pics[0], box_new, pics[1], (sx, sy, tx, ty)))
    widget._fade_pictures = (key, prepared, result)
    return result


def _draw_mixed(painter, pictures, tt):
    """Each group's old and new pictures mixed at tt (premultiplied, as _mix does per
    cell), slid and scaled by tt of the group's move. The mix is made on the picture of the
    side that weighs more (the old one first, the new one from halfway), so each end is
    shown as drawn, pixel for pixel."""
    from aqt.qt import QPixmap

    def _lerp(a, b, t):
        return QRectF(
            a.x() + (b.x() - a.x()) * t,
            a.y() + (b.y() - a.y()) * t,
            a.width() + (b.width() - a.width()) * t,
            a.height() + (b.height() - a.height()) * t,
        )

    def _apply(r, sx, sy, tx, ty, inverse=False):
        if inverse:
            return QRectF((r.x() - tx) / sx, (r.y() - ty) / sy, r.width() / sx, r.height() / sy)
        return QRectF(r.x() * sx + tx, r.y() * sy + ty, r.width() * sx, r.height() * sy)

    def _in_pixels(r, box, pm):
        """r (logical) in the pixels of the picture pm covering box."""
        kx = pm.width() / box.width()
        ky = pm.height() / box.height()
        return QRectF((r.x() - box.x()) * kx, (r.y() - box.y()) * ky, r.width() * kx, r.height() * ky)

    tt = max(0.0, min(1.0, tt))
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    for box_old, pm_old, box_new, pm_new, (sx, sy, tx, ty) in pictures:
        if tt < 0.5:
            base, base_box, other, other_box = pm_old, box_old, pm_new, _apply(box_new, sx, sy, tx, ty, inverse=True)
            base_t, other_t = 1.0 - tt, tt
            at = _lerp(box_old, _apply(box_old, sx, sy, tx, ty), tt)
        else:
            base, base_box, other, other_box = pm_new, box_new, pm_old, _apply(box_old, sx, sy, tx, ty)
            base_t, other_t = tt, 1.0 - tt
            at = _lerp(_apply(box_new, sx, sy, tx, ty, inverse=True), box_new, tt)
        mix = QPixmap(base.size())
        mix.fill(Qt.GlobalColor.transparent)
        q = QPainter(mix)
        q.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        q.setOpacity(base_t)
        q.drawPixmap(0, 0, base)
        part = QPixmap(base.size())
        part.fill(Qt.GlobalColor.transparent)
        r = QPainter(part)
        r.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r.setOpacity(other_t)
        r.drawPixmap(_in_pixels(other_box, base_box, base), other, QRectF(0, 0, other.width(), other.height()))
        r.end()
        q.setOpacity(1.0)
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        q.drawPixmap(0, 0, part)
        q.end()
        painter.drawPixmap(at, mix, QRectF(0, 0, mix.width(), mix.height()))
    painter.restore()


def _draw_transition_cells_from_pairs(widget, painter, pairs, tt, include_empty_pairs=False):
    painter.setPen(Qt.PenStyle.NoPen)
    if not pairs:
        return
    prepared = _prepared_pairs(widget, pairs, include_empty_pairs)
    # The last frame is drawn cell by cell: exactly the chart that follows.
    pictures = _fade_pictures(widget, painter, prepared) if tt < 0.999 else None
    if pictures is not None:
        _draw_mixed(painter, pictures, tt)
        return
    for kind, rect0, o, n, r_old, r_new, c_old, c_new, p_old, p_new, same_rect, same_color in prepared:
        if kind in ("old", "new"):
            # A cell only on one side fades out (old) or in (new) where it is.
            color = QColor(c_old)
            color.setAlpha(int(c_old.alpha() * ((1.0 - tt) if kind == "old" else tt)))
            painter.setBrush(color)
            painter.drawRoundedRect(rect0, r_old, r_old)
            continue
        if kind == "mix" and same_rect:
            painter.setBrush(c_old if same_color else _mix(p_old, p_new, tt))
            painter.drawRoundedRect(rect0, r_old, r_old)
            continue
        rect = QRectF(
            o[0] + (n[0] - o[0]) * tt,
            o[1] + (n[1] - o[1]) * tt,
            o[2] + (n[2] - o[2]) * tt,
            o[3] + (n[3] - o[3]) * tt,
        )
        radius = r_old + (r_new - r_old) * tt
        if kind == "in":
            color = QColor(c_new)
            color.setAlpha(int(c_new.alpha() * tt))
        elif kind == "out":
            color = QColor(c_old)
            color.setAlpha(int(c_old.alpha() * (1.0 - tt)))
        else:
            color = c_old if same_color else _mix(p_old, p_new, tt)
        painter.setBrush(color)
        painter.drawRoundedRect(rect, radius, radius)


def render_labels_to_pixmap_impl(widget):
    from aqt.qt import QPixmap

    cache_key = _labels_cache_key(widget)
    cached = getattr(widget, "_labels_pixmap_cache", None)
    if cached is not None and not exporting() and getattr(widget, "_labels_pixmap_cache_key", None) == cache_key:
        return cached

    dpr = raster_dpr(widget)  # export: built at the export's resolution
    w = int(widget.width() * dpr)
    h = int(widget.height() * dpr)
    if w <= 0 or h <= 0:
        return None

    pixmap = QPixmap(w, h)
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    t_colors = get_theme_colors(widget)
    text_col = t_colors["text"]
    painter.setPen(text_col)

    if years_ops.is_years(widget):
        years_ops.draw_labels(widget, painter, month_short)
        painter.end()
        if not exporting():
            widget._labels_pixmap_cache = pixmap
            widget._labels_pixmap_cache_key = cache_key
        return pixmap

    if widget.view_mode == "continuous":
        if widget._effective_show_labels:
            cell_size, spacing, step, gap_width, label_space, margin_top, start_x, months_list = widget._get_continuous_layout()
            start_y = margin_top
            font = painter.font()
            font.setPointSize(max(6, min(8, int(cell_size * 0.7))))
            painter.setFont(font)

            current_x = start_x
            for (_yr, mo, _start_col, num_cols, _days_in_month, _first_day) in months_list:
                label_text = month_short(mo)
                painter.drawText(
                    QRectF(current_x, start_y - (16 * widget.scale), 70 * widget.scale, 15 * widget.scale),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
                    label_text,
                )
                current_x += num_cols * step + gap_width

            lx = start_x - label_space + 2 * widget.scale
            day_labels = _day_labels(widget.monday_first, (cell_size / widget.scale) < 11.0)
            for i, day_name in enumerate(day_labels):
                y = start_y + (i * 2 + 1) * step + (cell_size * 0.8)
                painter.drawText(int(lx), int(y), day_name)
        painter.end()
        return pixmap

    if not widget.hide_labels:
        cell_size, spacing, start_x, start_y, label_space = widget._get_grid_geometry()
        step = cell_size + spacing
        grid_start, in_range = widget._compute_grid_info()
        rendered_months = set()

        font = painter.font()
        font.setPointSize(max(6, min(8, int(cell_size * 0.7))))
        painter.setFont(font)
        for week in range(53):
            week_x = start_x + week * step
            for day in range(7):
                curr_date = grid_start + timedelta(weeks=week, days=day)
                if not in_range(curr_date):
                    continue
                m_key = (curr_date.year, curr_date.month)
                if m_key not in rendered_months:
                    painter.drawText(
                        QRectF(week_x, start_y - (16 * widget.scale), 50 * widget.scale, 15 * widget.scale),
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
                        month_short(curr_date.month),
                    )
                    rendered_months.add(m_key)

        label_x = start_x - label_space + (2 * widget.scale)
        day_labels = _day_labels(widget.monday_first, (cell_size / widget.scale) < 11.0)
        for i, day_name in enumerate(day_labels):
            y = start_y + (i * 2 + 1) * step + (cell_size * 0.8)
            painter.drawText(int(label_x), int(y), day_name)

    painter.end()
    if not exporting():  # keep the screen-resolution cache
        widget._labels_pixmap_cache = pixmap
        widget._labels_pixmap_cache_key = cache_key
    return pixmap


def render_scaffold_to_pixmap_impl(widget):
    from aqt.qt import QPixmap

    cache_key = _scaffold_cache_key(widget)
    cached = getattr(widget, "_scaffold_pixmap_cache", None)
    if cached is not None and not exporting() and getattr(widget, "_scaffold_pixmap_cache_key", None) == cache_key:
        return cached

    dpr = raster_dpr(widget)  # export: built at the export's resolution
    w = int(widget.width() * dpr)
    h = int(widget.height() * dpr)
    if w <= 0 or h <= 0:
        return None

    pixmap = QPixmap(w, h)
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(widget._brush_for_color(widget.empty_color))

    if years_ops.is_years(widget):
        lay = years_ops.layout(widget)
        radius = (lay["cell"] / 2.0) * (widget.rounding / 100.0)
        for _d, rect in years_ops.iter_cells(widget):
            painter.drawRoundedRect(rect, radius, radius)
    elif widget.view_mode == "continuous":
        cell_size, _spacing, step, gap_width, _label_space, margin_top, start_x, months_list = widget._get_continuous_layout()
        radius = (cell_size / 2.0) * (widget.rounding / 100.0)
        current_x = start_x
        for (_yr, _mo, start_col, num_cols, days_in_month, first_day) in months_list:
            for col in range(num_cols):
                for row in range(7):
                    day_offset = col * 7 + row - start_col
                    if day_offset < 0 or day_offset >= days_in_month:
                        continue
                    x = current_x + col * step
                    y = margin_top + row * step
                    painter.drawRoundedRect(QRectF(x, y, cell_size, cell_size), radius, radius)
            current_x += num_cols * step + gap_width
    else:
        cell_size, spacing, start_x, start_y, _label_space = widget._get_grid_geometry()
        radius = (cell_size / 2.0) * (widget.rounding / 100.0)
        step = cell_size + spacing
        grid_start, in_range = widget._compute_grid_info()
        for week in range(53):
            week_x = start_x + (week * step)
            for day in range(7):
                curr_date = grid_start + timedelta(weeks=week, days=day)
                if not in_range(curr_date):
                    continue
                y = start_y + (day * step)
                painter.drawRoundedRect(QRectF(week_x, y, cell_size, cell_size), radius, radius)

    labels = widget._render_labels_to_pixmap()
    if labels:
        painter.drawPixmap(0, 0, labels)

    painter.end()
    if not exporting():  # keep the screen-resolution cache
        widget._scaffold_pixmap_cache = pixmap
        widget._scaffold_pixmap_cache_key = cache_key
    return pixmap


def render_to_pixmap_impl(widget, data_source=None):
    from aqt.qt import QPixmap

    if data_source is None:
        data_source = widget.data

    dpr = raster_dpr(widget)  # export: built at the export's resolution
    w = int(widget.width() * dpr)
    h = int(widget.height() * dpr)

    if w <= 0 or h <= 0:
        return None

    pixmap = QPixmap(w, h)
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scaffold = widget._render_scaffold_to_pixmap()
    if scaffold:
        painter.drawPixmap(0, 0, scaffold)

    max_past_count, max_future_count = widget._get_max_counts(data_source)
    offset = rollover_hour()
    logical_today = (datetime.now() - timedelta(hours=offset)).date()
    painter.setPen(Qt.PenStyle.NoPen)

    if years_ops.is_years(widget):
        lay = years_ops.layout(widget)
        radius = (lay["cell"] / 2.0) * (widget.rounding / 100.0)
        for curr_date, rect in years_ops.iter_cells(widget):
            entry = data_source.get(curr_date.isoformat()[:10], 0)
            count, future = entry_counts(widget, entry)
            color = widget._resolve_cell_color(count, future, curr_date.date(), logical_today, max_past_count, max_future_count)
            if widget._is_empty_cell_color(color):
                continue
            painter.setBrush(widget._brush_for_color(color))
            painter.drawRoundedRect(rect, radius, radius)
    elif widget.view_mode == "continuous":
        cell_size, _spacing, step, gap_width, _label_space, margin_top, start_x, months_list = widget._get_continuous_layout()
        radius = (cell_size / 2.0) * (widget.rounding / 100.0)
        current_x = start_x
        for (_yr, _mo, start_col, num_cols, days_in_month, first_day) in months_list:
            for col in range(num_cols):
                for row in range(7):
                    day_offset = col * 7 + row - start_col
                    if day_offset < 0 or day_offset >= days_in_month:
                        continue
                    curr_date = first_day + timedelta(days=day_offset)
                    date_str = curr_date.isoformat()[:10]
                    entry = data_source.get(date_str, 0)
                    count, future = entry_counts(widget, entry)
                    color = widget._resolve_cell_color(count, future, curr_date.date(), logical_today, max_past_count, max_future_count)
                    if widget._is_empty_cell_color(color):
                        continue
                    x = current_x + col * step
                    y = margin_top + row * step
                    painter.setBrush(widget._brush_for_color(color))
                    painter.drawRoundedRect(QRectF(x, y, cell_size, cell_size), radius, radius)
            current_x += num_cols * step + gap_width
    else:
        cell_size, spacing, start_x, start_y, _label_space = widget._get_grid_geometry()
        step = cell_size + spacing
        grid_start, in_range = widget._compute_grid_info()
        radius = (cell_size / 2.0) * (widget.rounding / 100.0)
        for week in range(53):
            week_x = start_x + (week * step)
            for day in range(7):
                curr_date = grid_start + timedelta(weeks=week, days=day)
                if not in_range(curr_date):
                    continue
                date_str = curr_date.isoformat()[:10]
                entry = data_source.get(date_str, 0)
                count, future = entry_counts(widget, entry)
                color = widget._resolve_cell_color(
                    count,
                    future,
                    curr_date.date(),
                    logical_today,
                    max_past_count,
                    max_future_count,
                )
                if widget._is_empty_cell_color(color):
                    continue
                y = start_y + day * step
                painter.setBrush(widget._brush_for_color(color))
                painter.drawRoundedRect(QRectF(week_x, y, cell_size, cell_size), radius, radius)

    painter.end()
    return pixmap


def paint_event_impl(widget, event):
    painter = QPainter(widget)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    intro_t = max(0.0, min(1.0, float(widget.get_progress())))
    if intro_t < 0.999:
        painter.setOpacity(intro_t)

    # Years view scrolling inside its card: the cells stop above the legend.
    years_clip = None
    if years_ops.is_years(widget):
        try:
            lay = years_ops.layout(widget)
            # In a card of its own height (Deep Dive) the cells never go over the legend: when
            # they scroll, and while they move to a new place (an animation can start from
            # rows that were scrolled under it).
            if lay["max_scroll"] > 0 or years_ops.fits_height(widget):
                years_clip = QRectF(0.0, 0.0, float(widget.width()), float(lay["viewport_bottom"]))
                painter.save()
                painter.setClipRect(years_clip)
        except Exception:
            years_clip = None

    if widget._nav_transition_active:
        t = max(0.0, min(1.0, float(widget._nav_transition_progress)))
        width = widget.width()
        shift = t * width
        direction = widget._nav_transition_direction
        old_x = int(-direction * shift)
        new_x = int(direction * (width - shift))
        widget._draw_nav_transition_frame(painter, old_x, new_x)
    elif widget._mode_transition_active:
        t = max(0.0, min(1.0, float(widget._mode_transition_progress)))
        tt = t * t * (3.0 - (2.0 * t))
        _draw_transition_cells_from_pairs(
            widget,
            painter,
            getattr(widget, "_mode_transition_cell_pairs", None),
            tt,
            include_empty_pairs=True,
        )
        label_from = getattr(widget, "_years_label_from", None)
        if label_from is not None and years_ops.is_years(widget):
            # Years moving (fold, gap): the labels are drawn at each frame, sliding with their row.
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(get_theme_colors(widget)["text"])
            years_ops.draw_labels(widget, painter, month_short, motion=(label_from, tt))
            painter.restore()
        elif widget._mode_transition_old_labels_pixmap or widget._mode_transition_new_labels_pixmap:
            painter.save()
            if widget._mode_transition_old_labels_pixmap:
                painter.setOpacity(1.0 - tt)
                painter.drawPixmap(0, 0, widget._mode_transition_old_labels_pixmap)
            if widget._mode_transition_new_labels_pixmap:
                painter.setOpacity(tt)
                painter.drawPixmap(0, 0, widget._mode_transition_new_labels_pixmap)
            painter.restore()
    elif widget._data_transition_active:
        # The animation already eases the progress; easing again squeezed the whole fade into the middle of the run.
        tt = max(0.0, min(1.0, float(widget._transition_progress)))
        scaffold = widget._render_scaffold_to_pixmap()
        if scaffold:
            painter.drawPixmap(0, 0, scaffold)
        _draw_transition_cells_from_pairs(widget, painter, getattr(widget, "_transition_cell_pairs", None), tt)
    else:
        if exporting():
            frame = widget._render_to_pixmap()
        else:
            if widget._pixmap_cache is None:
                widget._pixmap_cache = widget._render_to_pixmap()
            frame = widget._pixmap_cache

        if frame:
            painter.drawPixmap(0, 0, frame)

    if years_clip is not None:
        painter.restore()
        years_ops.draw_scrollbar(widget, painter)

    if getattr(widget, "show_legend", False):
        from .legend import paint_legend

        paint_legend(widget, painter)

    if widget.hover_pos and not widget._mode_transition_active:
        hover_outline = get_hover_marker_outline_color(widget, prefer_pinned_contrast=True)
        mx = widget.hover_pos.x()
        my = widget.hover_pos.y()

        if years_ops.is_years(widget):
            hit = years_ops.hit_test(widget, mx, my)
            if hit:
                rect = hit[1]
                radius = (rect.width() / 2.0) * (widget.rounding / 100.0)
                painter.setPen(QPen(hover_outline, 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(rect, radius, radius)
        elif widget.view_mode == "continuous":
            hit = widget._continuous_hit_test(mx, my)
            if hit:
                _, _, col, row, block_start_x = hit
                cs, sp, step, gap_width, label_space, margin_top, start_x, months = widget._get_continuous_layout()
                x = block_start_x + col * step
                y = margin_top + row * step
                radius = (cs / 2.0) * (widget.rounding / 100.0)
                painter.setPen(QPen(hover_outline, 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(QRectF(x, y, cs, cs), radius, radius)
        else:
            cell_size, spacing, start_x, start_y, label_space = widget._get_grid_geometry()
            step = cell_size + spacing

            if mx >= start_x and my >= start_y:
                week_idx = int((mx - start_x) / step)
                day_idx = int((my - start_y) / step)

                if 0 <= week_idx <= 52 and 0 <= day_idx <= 6:
                    grid_start, in_range = widget._compute_grid_info()
                    target_date = grid_start + timedelta(weeks=week_idx, days=day_idx)

                    if in_range(target_date):
                        x = start_x + week_idx * step
                        y = start_y + day_idx * step
                        rect = QRectF(x, y, cell_size, cell_size)
                        painter.setPen(QPen(hover_outline, 2))
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                        radius = (cell_size / 2.0) * (widget.rounding / 100.0)
                        painter.drawRoundedRect(rect, radius, radius)
