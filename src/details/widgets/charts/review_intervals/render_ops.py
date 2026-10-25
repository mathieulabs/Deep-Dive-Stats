# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..common.cache_dpr import cache_dpr, cache_surface, draw_cache, stale_cache
from aqt.qt import QColor, QPainter, QRectF, Qt

from ...chart_utils.drawing import chart_style, draw_bar_rect
from ...chart_utils.theme import get_theme_colors, is_night_mode
from ..common.discrete import (
    build_discrete_gradient_color,
    draw_cached_discrete_scaffold,
    finalize_discrete_transition_state,
    finalize_discrete_bar_color,
    prepare_discrete_paint_state,
    resolve_discrete_bar_draw_state,
    resolve_discrete_bar_geometry,
)
from ..common.stats import draw_chart_bottom_stats
from ..common.cache_keys import series_cache_token as _series_cache_token, theme_color_token as _theme_color_token
from ..common.discrete.cumulative import draw_cumulative_area_impl


def _draw_cached_chrome(widget, painter, *, width, height, plot_w, plot_h, margin_left, margin_top, margin_bottom, draw_values):
    theme = get_theme_colors(widget)
    stats = widget.get_stats_text() if getattr(widget, "show_stats", False) else []
    cache_key = (
        chart_style(widget),  # line opacity setting (Total / Average lines)
        int(width),
        int(height),
        int(round(float(plot_w))),
        int(round(float(plot_h))),
        int(margin_left),
        int(margin_top),
        int(margin_bottom),
        int(getattr(widget, "max_days", 0) or 0),
        int(getattr(widget, "_points_count", 0) or 0),
        _series_cache_token(draw_values),
        bool(getattr(widget, "cumulative_visible", True)),
        bool(getattr(widget, "show_stats", False)),
        tuple(str(s) for s in stats),
        _theme_color_token(theme.get("text")),
        _theme_color_token(theme.get("text_secondary")),
        _theme_color_token(theme.get("total_line")),
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
            if getattr(widget, "cumulative_visible", True):
                total_cards = sum(float(v or 0.0) for v in (draw_values or [])) or 1.0
                widget.draw_cumulative_area(cp, plot_w, plot_h, margin_left, margin_top, total_cards)
            widget.draw_x_axis(cp, plot_w, height, margin_left, margin_bottom)
            widget.draw_stats_text(cp, plot_w, height, margin_left, margin_bottom)
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

    t = widget.get_progress()

    state = prepare_discrete_paint_state(widget, painter, t=t)
    axis_max = state["axis_max"]
    draw_values = state["draw_values"]
    margin_left = state["margin_left"]
    margin_right = state["margin_right"]
    margin_top = state["margin_top"]
    margin_bottom = state["margin_bottom"]
    plot_w = state["plot_w"]
    plot_h = state["plot_h"]
    total_cards = state["total_cards"]

    draw_cached_discrete_scaffold(
        widget,
        painter,
        width=w,
        height=h,
        margin_left=margin_left,
        margin_top=margin_top,
        margin_right=margin_right,
        margin_bottom=margin_bottom,
        axis_max=axis_max,
        max_cumulative=(total_cards if getattr(widget, "show_cumulative_axis", True) else None),
    )

    widget.draw_bars(painter, plot_w, plot_h, margin_left, margin_top)
    use_cached_chrome = (
        (not widget._data_transition_active)
        and float(t) < 0.999
        and int(getattr(widget, "hover_index", -1)) == -1
    )
    if use_cached_chrome:
        _draw_cached_chrome(
            widget,
            painter,
            width=w,
            height=h,
            plot_w=plot_w,
            plot_h=plot_h,
            margin_left=margin_left,
            margin_top=margin_top,
            margin_bottom=margin_bottom,
            draw_values=draw_values,
        )
    else:
        if getattr(widget, "cumulative_visible", True):
            widget.draw_cumulative_area(painter, plot_w, plot_h, margin_left, margin_top, total_cards)
        widget.draw_x_axis(painter, plot_w, h, margin_left, margin_bottom)
        widget.draw_stats_text(painter, plot_w, h, margin_left, margin_bottom)

    finalize_discrete_transition_state(widget, t=t)


def draw_bars_impl(widget, painter, plot_w, plot_h, margin_left, margin_top):
    draw_values = getattr(widget, "_anim_draw_values", widget._display_values)
    draw_ratios = getattr(widget, "_anim_draw_ratios", [])
    points_count = int(getattr(widget, "_anim_draw_points_count", widget._points_count) or 0)
    if points_count <= 0:
        return

    base_color = QColor(widget.bar_color)
    t = widget.get_progress()
    step_x, bar_w, slots, intro = resolve_discrete_bar_draw_state(
        widget,
        plot_w=plot_w,
        points_count=points_count,
        margin_left=margin_left,
        t=t,
        width_ratio=0.95,
    )

    painter.setPen(Qt.PenStyle.NoPen)
    for i in range(points_count):
        val = draw_values[i] if i < len(draw_values) else 0.0
        if val <= 0:
            continue
        x, cur_w = resolve_discrete_bar_geometry(
            i,
            step_x=step_x,
            bar_w=bar_w,
            slots=slots,
            margin_left=margin_left,
        )
        ratio_for_height = draw_ratios[i] if i < len(draw_ratios) else (val / max(1.0, widget.max_val))
        bar_h = ratio_for_height * plot_h * intro
        y = margin_top + plot_h - bar_h
        bar_center_x = x + (cur_w / 2.0)

        ratio = (bar_center_x - margin_left) / max(1.0, float(plot_w))
        dark = is_night_mode(widget)
        c = build_discrete_gradient_color(base_color, ratio=ratio, dark=dark)
        c = finalize_discrete_bar_color(
            c,
            dark=dark,
            hovered=(i == widget.hover_index),
            opacity_pct=getattr(widget, "chart_opacity_pct", 100),
        )
        painter.setBrush(c)
        draw_bar_rect(painter, QRectF(x, y, cur_w, bar_h), widget=widget)


def draw_x_axis_impl(widget, painter, plot_w, total_h, margin_left, margin_bottom):
    painter.setPen(get_theme_colors(widget).get("text_secondary", QColor("#888888")))
    font = painter.font()
    font.setPixelSize(10)
    painter.setFont(font)

    last_label = None
    for i in range(0, 6):
        day = 1 + int((i / 5.0) * (widget.max_days - 1))
        label = f"{day}"
        if label == last_label:
            continue
        last_label = label

        x = margin_left + (i / 5.0 * plot_w)
        if i == 0:
            t_rect = QRectF(margin_left, total_h - margin_bottom + 5, 30, 15)
            align = Qt.AlignmentFlag.AlignLeft
        elif i == 5:
            t_rect = QRectF(x - 30, total_h - margin_bottom + 5, 30, 15)
            align = Qt.AlignmentFlag.AlignRight
        else:
            t_rect = QRectF(x - 15, total_h - margin_bottom + 5, 30, 15)
            align = Qt.AlignmentFlag.AlignCenter
        painter.drawText(t_rect, align, label)


def draw_stats_text_impl(widget, painter, plot_w, h, margin_left, margin_bottom):
    return draw_chart_bottom_stats(widget, painter, plot_w, h, margin_left, margin_bottom)
