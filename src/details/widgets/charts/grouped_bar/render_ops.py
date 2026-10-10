# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..common.cache_dpr import cache_dpr, cache_surface, draw_cache, stale_cache
from aqt.qt import QColor, QPainter, QPen, QRect, QRectF, Qt

from ...chart_utils import ChartGeometry, draw_grid_and_axes, get_theme_colors
from ...chart_utils.drawing import chart_axes_style
from ..common.cache_keys import theme_color_token as _theme_color_token


def _draw_cached_scaffold(widget, painter, *, width, height, margin_left, margin_top, margin_right, margin_bottom, axis_max):
    theme = get_theme_colors(widget)
    cache_key = (
        int(width),
        int(height),
        int(margin_left),
        int(margin_top),
        int(margin_right),
        int(margin_bottom),
        int(round(float(axis_max or 0.0))),
        _theme_color_token(theme.get("text")),
        _theme_color_token(theme.get("grid")),
        chart_axes_style(widget),  # Settings > Chart Style: grid / quiet axes
        str(widget.font().family()),
    )
    pixmap = getattr(widget, "_scaffold_cache_pixmap", None)
    if pixmap is None or stale_cache(pixmap) or getattr(widget, "_scaffold_cache_key", None) != cache_key or pixmap.devicePixelRatio() + 0.01 < cache_dpr(widget, painter):
        dpr = 1.0
        try:
            dpr = cache_dpr(widget, painter)
        except Exception:
            dpr = 1.0
        px = cache_surface(max(1, int(round(width * dpr))), max(1, int(round(height * dpr))))
        px.setDevicePixelRatio(dpr)
        px.fill(Qt.GlobalColor.transparent)
        sp = QPainter(px)
        try:
            sp.setRenderHint(QPainter.RenderHint.Antialiasing)
            draw_grid_and_axes(
                sp,
                width,
                height,
                margin_left,
                margin_top,
                margin_right,
                margin_bottom,
                axis_max,
                widget=widget,
            )
        finally:
            sp.end()
        widget._scaffold_cache_key = cache_key
        widget._scaffold_cache_pixmap = px
        pixmap = px
    if pixmap is not None:
        draw_cache(painter, pixmap)


def _draw_cached_chrome(widget, painter, *, width, height, margin_left, margin_top, margin_bottom, group_width, group_labels_rects):
    theme = get_theme_colors(widget)
    cache_key = (
        int(width),
        int(height),
        int(margin_left),
        int(margin_top),
        int(margin_bottom),
        int(round(float(group_width or 0.0))),
        tuple((int(r.x()), int(r.y()), int(r.width()), int(r.height()), str(label)) for r, label in (group_labels_rects or [])),
        _theme_color_token(theme.get("text")),
        str(widget.font().family()),
    )
    pixmap = getattr(widget, "_chrome_cache_pixmap", None)
    if pixmap is None or stale_cache(pixmap) or getattr(widget, "_chrome_cache_key", None) != cache_key or pixmap.devicePixelRatio() + 0.01 < cache_dpr(widget, painter):
        dpr = 1.0
        try:
            dpr = cache_dpr(widget, painter)
        except Exception:
            dpr = 1.0
        px = cache_surface(max(1, int(round(width * dpr))), max(1, int(round(height * dpr))))
        px.setDevicePixelRatio(dpr)
        px.fill(Qt.GlobalColor.transparent)
        cp = QPainter(px)
        try:
            cp.setRenderHint(QPainter.RenderHint.Antialiasing)
            is_dark = bool(theme.get("is_dark"))
            line_pen = QPen(QColor(255, 255, 255, 10) if is_dark else QColor(0, 0, 0, 10))
            line_pen.setStyle(Qt.PenStyle.DashLine)
            n_groups = len(widget._group_order)
            for i in range(1, n_groups):
                group_x = margin_left + (i * group_width)
                cp.setPen(line_pen)
                cp.drawLine(int(group_x), margin_top, int(group_x), height - margin_bottom)

            font = cp.font()
            font.setBold(True)
            font.setPointSize(9)
            cp.setFont(font)
            cp.setPen(theme.get("text"))
            for rect, label in group_labels_rects:
                cp.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)
        finally:
            cp.end()
        widget._chrome_cache_key = cache_key
        widget._chrome_cache_pixmap = px
        pixmap = px
    if pixmap is not None:
        draw_cache(painter, pixmap)


def paint_event_impl(widget, event):
    painter = QPainter(widget)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    w = widget.width()
    h = widget.height()
    if not hasattr(widget, "margins"):
        widget._recalculate_layout()

    margin_top = ChartGeometry.MARGIN_TOP
    margin_bottom = ChartGeometry.MARGIN_BOTTOM

    theme = get_theme_colors(widget)
    is_dark = theme["is_dark"]
    text_col = theme["text"]

    values_for_draw = widget._flatten_grouped_values(widget.data)
    axis_max = widget.max_val
    draw_ratios = [max(0.0, (v / max(1.0, axis_max))) for v in values_for_draw]
    if widget._data_transition_active:
        t = widget.get_progress()
        if t >= 0.995:
            t = 1.0
        old_values = widget._transition_old_values or []
        new_values = widget._transition_new_values or []
        old_max = max(old_values) if old_values else 0.0
        new_max = max(new_values) if new_values else 0.0
        old_scale = max(1.0, old_max)
        new_scale = max(1.0, new_max)
        axis_max = max(1.0, old_max + ((new_max - old_max) * t))
        values_for_draw = widget._interpolate_series_fast(old_values, new_values, t)
        draw_ratios = []
        for ov, nv in zip(old_values, new_values):
            r0 = max(0.0, ov / old_scale)
            r1 = max(0.0, nv / new_scale)
            rr = r0 + ((r1 - r0) * t)
            draw_ratios.append(max(0.0, min(1.0, rr)))

    margin_right = ChartGeometry.DEFAULT_MARGIN_RIGHT
    fm = widget.fontMetrics()
    margin_left = ChartGeometry.calculate_dynamic_left_margin(fm, axis_max)
    if widget._data_transition_active:
        old_left = ChartGeometry.calculate_dynamic_left_margin(fm, max(1.0, widget._transition_old_max))
        new_left = ChartGeometry.calculate_dynamic_left_margin(fm, max(1.0, widget._transition_new_max))
        margin_left = int(round(old_left + ((new_left - old_left) * t)))

    avail_h = h - margin_top - margin_bottom
    n_groups = len(widget._group_order)
    avail_w = w - margin_left - margin_right
    group_width = avail_w / n_groups if n_groups > 0 else 0

    bar_rects = []
    group_labels_rects = []
    bar_spacing = 4
    group_padding = 20
    bar_w = (group_width - group_padding * 2 - (len(widget.colors) - 1) * bar_spacing) / len(widget.colors) if n_groups > 0 else 0
    if bar_w < 2:
        bar_w = 2
    for i, group_key in enumerate(widget._group_order):
        group_x = margin_left + (i * group_width)
        label_rect = QRect(int(group_x), h - margin_bottom + 5, int(group_width), 20)
        group_labels_rects.append((label_rect, widget.group_labels.get(group_key, group_key)))
        values = widget.data.get(group_key, [0, 0, 0, 0])
        start_x = group_x + group_padding
        for b_idx, val in enumerate(values):
            x = start_x + (b_idx * (bar_w + bar_spacing))
            bar_h_full = (val / widget.max_val) * avail_h if widget.max_val > 0 else 0
            rect = QRectF(x, margin_top + avail_h - bar_h_full, bar_w, bar_h_full)
            bar_rects.append({"group": group_key, "btn_idx": b_idx, "val": val, "rect": rect, "color": QColor(widget.colors[b_idx])})

    _draw_cached_scaffold(
        widget,
        painter,
        width=w,
        height=h,
        margin_left=margin_left,
        margin_top=margin_top,
        margin_right=margin_right,
        margin_bottom=margin_bottom,
        axis_max=axis_max,
    )

    intro = 1.0 if widget._data_transition_active else max(0.0, min(1.0, float(widget.get_progress())))
    for idx, bar in enumerate(bar_rects):
        full_rect = bar["rect"]
        ratio = draw_ratios[idx] if idx < len(draw_ratios) else 0.0
        h_anim = ratio * avail_h * intro
        y_anim = margin_top + avail_h - h_anim
        bar_rect = QRectF(full_rect.x(), y_anim, full_rect.width(), h_anim)
        color = QColor(bar["color"])
        color.setAlpha(int(getattr(widget, "chart_opacity_pct", 100) * 2.55))
        if widget.hover_info and bar["rect"] == widget.hover_info[3]:
            color = color.lighter(130) if is_dark else color.darker(115)

        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(bar_rect, 2, 2)

    use_cached_chrome = (not widget._data_transition_active) and (widget.hover_info is None)
    if use_cached_chrome:
        _draw_cached_chrome(
            widget,
            painter,
            width=w,
            height=h,
            margin_left=margin_left,
            margin_top=margin_top,
            margin_bottom=margin_bottom,
            group_width=group_width,
            group_labels_rects=group_labels_rects,
        )
    else:
        line_pen = QPen(QColor(255, 255, 255, 10) if is_dark else QColor(0, 0, 0, 10))
        line_pen.setStyle(Qt.PenStyle.DashLine)
        for i in range(1, n_groups):
            group_x = margin_left + (i * group_width)
            painter.setPen(line_pen)
            painter.drawLine(int(group_x), margin_top, int(group_x), h - margin_bottom)

        font = painter.font()
        font.setBold(True)
        font.setPointSize(9)
        painter.setFont(font)
        painter.setPen(text_col)
        for rect, label in group_labels_rects:
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

    if widget._data_transition_active and widget.get_progress() >= 0.999:
        widget._data_transition_active = False
        widget._transition_old_values = []
        widget._transition_new_values = []
        widget._transition_old_max = 1.0
        widget._transition_new_max = 1.0
