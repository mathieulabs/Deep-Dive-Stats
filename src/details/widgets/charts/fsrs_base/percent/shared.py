# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ...common.cache_dpr import cache_dpr, cache_surface, draw_cache, stale_cache
from aqt.qt import QColor, QPainter, QRectF, Qt

from ....chart_utils.theme import get_theme_colors
from ....chart_utils.drawing import draw_bar_rect
from ....chart_utils.tooltip import hide_tooltip_targets, show_tooltip_text_near
from ...common.stats.render import draw_chart_bottom_stats
from ...common.cache_keys import theme_color_token as _theme_color_token


def lerp_fsrs_percent_color(c1: QColor, c2: QColor, t: float) -> QColor:
    r = int(c1.red() + t * (c2.red() - c1.red()))
    g = int(c1.green() + t * (c2.green() - c1.green()))
    b = int(c1.blue() + t * (c2.blue() - c1.blue()))
    return QColor(r, g, b)


def load_fsrs_gradient_colors(widget):
    from .....ui import Config, get_chart_color

    widget._color_low = QColor(get_chart_color(Config.COLOR_GRADIENT_LOW, widget))
    widget._color_high = QColor(get_chart_color(Config.COLOR_GRADIENT_HIGH, widget))


def refresh_fsrs_gradient_colors(widget):
    widget._load_gradient_colors()
    widget.update()


def _get_cached_fsrs_percent_bar_colors(widget, *, reverse_gradient=False):
    low = getattr(widget, "_color_low", QColor("#ff3b30"))
    high = getattr(widget, "_color_high", QColor("#4cd964"))
    alpha = int(getattr(widget, "chart_opacity_pct", 100) * 2.55)
    cache_key = (
        int(low.rgba()),
        int(high.rgba()),
        int(alpha),
        bool(reverse_gradient),
    )
    colors = getattr(widget, "_bar_color_cache", None)
    if colors is None or getattr(widget, "_bar_color_cache_key", None) != cache_key:
        built = []
        for pct in range(101):
            if reverse_gradient:
                c = lerp_fsrs_percent_color(high, low, pct / 100.0)
            else:
                c = lerp_fsrs_percent_color(low, high, pct / 100.0)
            c.setAlpha(alpha)
            built.append(c)
        widget._bar_color_cache_key = cache_key
        widget._bar_color_cache = built
        colors = built
    return colors or []


def _draw_cached_fsrs_percent_chrome(widget, painter, *, plot_w, width, height, margin_left, margin_bottom):
    theme = get_theme_colors(widget)
    stats = widget.get_stats_text()
    cache_key = (
        int(width),
        int(height),
        int(round(float(plot_w or 0.0))),
        int(margin_left),
        int(margin_bottom),
        tuple(str(x) for x in (stats or [])),
        _theme_color_token(theme.get("text")),
        _theme_color_token(theme.get("text_secondary")),
        str(widget.font().family()),
        int(getattr(widget, "total_cards", 0)),
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
            cp.setPen(theme.get("text_secondary", QColor("#888888")))
            font = cp.font()
            font.setPixelSize(9)
            cp.setFont(font)
            for i in range(0, 101, 20):
                x = margin_left + (i * plot_w / 101)
                t_rect = QRectF(x - 15, height - margin_bottom + 5, 30, 15)
                cp.drawText(t_rect, Qt.AlignmentFlag.AlignCenter, f"{i}%")
            draw_chart_bottom_stats(
                widget,
                cp,
                plot_w,
                height,
                margin_left,
                margin_bottom,
                require_positive_total=True,
            )
        finally:
            cp.end()
        widget._chrome_cache_key = cache_key
        widget._chrome_cache_pixmap = px
        pixmap = px

    if pixmap is not None:
        draw_cache(painter, pixmap)


def resolve_fsrs_percent_hover_index(widget, pos, *, exact_match=False):
    if not widget.data_list:
        return -1

    w = widget.width()
    h = widget.height()
    margin_left, margin_right, margin_bottom, margin_top = widget._get_margins()
    plot_w = w - margin_left - margin_right
    if plot_w <= 0:
        return -1

    if not (margin_left <= pos.x() <= w - margin_right and margin_top <= pos.y() <= h - margin_bottom):
        return -1

    step_x = plot_w / 101
    if exact_match:
        pct_hovered = int((pos.x() - margin_left) / step_x)
        pct_hovered = max(0, min(100, pct_hovered))
        for i, (pct, _count) in enumerate(widget.data_list):
            if pct == pct_hovered:
                return i
        return -1

    closest_idx = -1
    min_dist = 9999.0
    for i, (pct, _count) in enumerate(widget.data_list):
        x_center = margin_left + (pct * step_x) + (step_x / 2)
        dist = abs(pos.x() - x_center)
        if dist < min_dist:
            min_dist = dist
            closest_idx = i
    if closest_idx != -1 and min_dist <= max(step_x, 4.0):
        return closest_idx
    return -1


def mouse_move_fsrs_percent_chart(widget, event, *, exact_match=False, clear_outside_plot=False):
    if not widget.data_list:
        return

    found_idx = resolve_fsrs_percent_hover_index(widget, event.pos(), exact_match=exact_match)
    if found_idx == -1 and clear_outside_plot:
        pos = event.pos()
        w = widget.width()
        h = widget.height()
        margin_left, margin_right, margin_bottom, margin_top = widget._get_margins()
        inside_plot = margin_left <= pos.x() <= w - margin_right and margin_top <= pos.y() <= h - margin_bottom
        if not inside_plot:
            widget._clear_hover()
            return

    if widget.hover_index != found_idx:
        widget.hover_index = found_idx
        widget.update()

    if found_idx != -1:
        k, v = widget.data_list[found_idx]
        text = widget.get_tooltip_text(k, v)
        show_tooltip_text_near(
            widget,
            widget.tooltip_window,
            event.pos(),
            text,
            x_offset=15,
            y_offset=15,
            show_only_if_hidden=True,
        )
    else:
        hide_tooltip_targets(widget, "tooltip_window")


def draw_fsrs_percent_bars(
    widget,
    painter,
    plot_w,
    plot_h,
    margin_left,
    margin_top,
    *,
    reverse_gradient=False,
):
    if not widget.data_list:
        return

    step_x = plot_w / 101
    bar_w = step_x * 0.95
    if bar_w < 1:
        bar_w = 1
    draw_ratios = getattr(widget, "_anim_draw_ratios", [])
    is_dark = bool(get_theme_colors(widget).get("is_dark"))
    base_colors = _get_cached_fsrs_percent_bar_colors(widget, reverse_gradient=reverse_gradient)

    painter.setPen(Qt.PenStyle.NoPen)
    for i, (pct, count) in enumerate(widget.data_list):
        x = margin_left + (pct * step_x) + (step_x - bar_w) / 2
        ratio_for_height = draw_ratios[i] if i < len(draw_ratios) else (count / max(1.0, widget.max_val))
        bar_h = ratio_for_height * plot_h
        y = margin_top + plot_h - bar_h

        c = QColor(base_colors[pct] if 0 <= pct < len(base_colors) else QColor("#888888"))
        if i == widget.hover_index:
            c = c.lighter(130) if is_dark else c.darker(115)
            c.setAlpha(255)
        painter.setBrush(c)
        draw_bar_rect(painter, QRectF(x, y, bar_w, bar_h), widget=widget)


def draw_fsrs_percent_extras(widget, painter, plot_w, margin_left, margin_bottom, h):
    use_cached_chrome = (
        (not bool(getattr(widget, "_data_transition_active", False)))
        and int(getattr(widget, "hover_index", -1)) == -1
    )
    if use_cached_chrome:
        _draw_cached_fsrs_percent_chrome(
            widget,
            painter,
            plot_w=plot_w,
            width=widget.width(),
            height=h,
            margin_left=margin_left,
            margin_bottom=margin_bottom,
        )
        return

    painter.setPen(get_theme_colors(widget).get("text_secondary", QColor("#888888")))
    font = painter.font()
    font.setPixelSize(9)
    painter.setFont(font)

    for i in range(0, 101, 20):
        x = margin_left + (i * plot_w / 101)
        t_rect = QRectF(x - 15, h - margin_bottom + 5, 30, 15)
        painter.drawText(t_rect, Qt.AlignmentFlag.AlignCenter, f"{i}%")

    return draw_chart_bottom_stats(
        widget,
        painter,
        plot_w,
        h,
        margin_left,
        margin_bottom,
        require_positive_total=True,
    )
