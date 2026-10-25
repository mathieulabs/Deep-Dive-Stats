# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..common.cache_dpr import exporting, raster_dpr
from datetime import datetime, timedelta

from aqt.qt import QColor, QPainter, QPen, QRectF, Qt

from ....ui import rollover_hour
from ...chart_utils import get_theme_colors
from ...chart_utils.drawing import get_hover_marker_outline_color
from ..common.cache_keys import theme_color_token as _theme_color_token
from .metrics import entry_counts


def _geometry_token(widget):
    """Where the grid is drawn now: a cached picture is only valid for this exact layout."""
    try:
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


def _draw_transition_cells_from_pairs(widget, painter, pairs, tt, include_empty_pairs=False):
    painter.setPen(Qt.PenStyle.NoPen)
    if not pairs:
        return
    for kind, rect0, o, n, r_old, r_new, c_old, c_new, p_old, p_new, same_rect, same_color in _prepared_pairs(
        widget, pairs, include_empty_pairs
    ):
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

    if widget.view_mode == "continuous":
        if widget._effective_show_labels:
            cell_size, spacing, step, gap_width, label_space, margin_top, start_x, months_list = widget._get_continuous_layout()
            start_y = margin_top
            month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            font = painter.font()
            font.setPointSize(max(6, min(8, int(cell_size * 0.7))))
            painter.setFont(font)

            current_x = start_x
            for (_yr, mo, _start_col, num_cols, _days_in_month, _first_day) in months_list:
                label_text = month_names[mo - 1]
                painter.drawText(
                    QRectF(current_x, start_y - (16 * widget.scale), 70 * widget.scale, 15 * widget.scale),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
                    label_text,
                )
                current_x += num_cols * step + gap_width

            lx = start_x - label_space + 2 * widget.scale
            if (cell_size / widget.scale) < 11.0:
                day_labels = ["T", "T", "S"] if widget.monday_first else ["M", "W", "F"]
            else:
                day_labels = ["Tue", "Thu", "Sat"] if widget.monday_first else ["Mon", "Wed", "Fri"]
            for i, day_name in enumerate(day_labels):
                y = start_y + (i * 2 + 1) * step + (cell_size * 0.8)
                painter.drawText(int(lx), int(y), day_name)
        painter.end()
        return pixmap

    if not widget.hide_labels:
        cell_size, spacing, start_x, start_y, label_space = widget._get_grid_geometry()
        step = cell_size + spacing
        grid_start, in_range = widget._compute_grid_info()
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
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
                        months[curr_date.month - 1],
                    )
                    rendered_months.add(m_key)

        label_x = start_x - label_space + (2 * widget.scale)
        if (cell_size / widget.scale) < 11.0:
            day_labels = ["T", "T", "S"] if widget.monday_first else ["M", "W", "F"]
        elif widget.monday_first:
            day_labels = ["Tue", "Thu", "Sat"]
        else:
            day_labels = ["Mon", "Wed", "Fri"]
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

    if widget.view_mode == "continuous":
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

    if widget.view_mode == "continuous":
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
        if widget._mode_transition_old_labels_pixmap or widget._mode_transition_new_labels_pixmap:
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

    if getattr(widget, "show_legend", False):
        from .legend import paint_legend

        paint_legend(widget, painter)

    if widget.hover_pos and not widget._mode_transition_active:
        hover_outline = get_hover_marker_outline_color(widget, prefer_pinned_contrast=True)
        mx = widget.hover_pos.x()
        my = widget.hover_pos.y()

        if widget.view_mode == "continuous":
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
