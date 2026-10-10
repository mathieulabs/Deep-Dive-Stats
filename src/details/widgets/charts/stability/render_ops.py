# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..common.cache_dpr import cache_dpr, cache_surface, draw_cache, stale_cache
from aqt.qt import QColor, QPainter, QRectF, Qt

from ...chart_utils.drawing import draw_bar_rect, draw_cumulative_line_and_area
from ...chart_utils.theme import get_theme_colors, is_night_mode
from ..common.discrete import (
    build_cumulative_paths,
    build_cumulative_points,
    build_default_line_x_positions,
    build_discrete_gradient_color,
    build_running_total_series,
    draw_cached_discrete_scaffold,
    finalize_discrete_bar_color,
    finalize_discrete_transition_state,
    prepare_discrete_paint_state,
    resolve_discrete_bar_draw_state,
    resolve_discrete_bar_geometry,
    resample_discrete_series,
)
from ..common.discrete.cumulative import normalized_running_total
from ..common.stats import draw_chart_bottom_stats
from ..common.cache_keys import series_cache_token as _series_cache_token, theme_color_token as _theme_color_token


def _draw_cached_chrome(widget, painter, *, width, height, plot_w, margin_left, margin_bottom, draw_values):
    theme = get_theme_colors(widget)
    stats = widget.get_stats_text() if getattr(widget, "show_stats", False) else []
    cache_key = (
        int(width),
        int(height),
        int(round(float(plot_w))),
        int(margin_left),
        int(margin_bottom),
        int(getattr(widget, "_display_bin_size", 1) or 1),
        int(getattr(widget, "_display_bins_count", 0) or 0),
        _series_cache_token(draw_values),
        bool(getattr(widget, "show_stats", False)),
        tuple(str(s) for s in stats),
        _theme_color_token(theme.get("text")),
        _theme_color_token(theme.get("text_secondary")),
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
            draw_extras_impl(
                widget,
                cp,
                plot_w,
                0,
                margin_left,
                0,
                margin_bottom,
                width,
                height,
            )
        finally:
            cp.end()
        widget._chrome_cache_key = cache_key
        widget._chrome_cache_pixmap = px
        pixmap = px

    if pixmap is not None:
        draw_cache(painter, pixmap)


def draw_bars_impl(widget, painter, plot_w, plot_h, margin_left, margin_top):
    draw_values = getattr(widget, "_anim_draw_values", widget._display_values)
    draw_ratios = getattr(widget, "_anim_draw_ratios", [])
    n = int(getattr(widget, "_anim_bins_count", widget._display_bins_count) or 0)
    if n <= 0:
        return

    base_color = QColor(widget.color)
    base_color.setAlpha(int(getattr(widget, "chart_opacity_pct", 100) * 2.55))
    t = widget.get_progress()
    step_x, bar_w, slots, intro = resolve_discrete_bar_draw_state(
        widget,
        plot_w=plot_w,
        points_count=n,
        margin_left=margin_left,
        t=t,
        width_ratio=0.95,
        transition_count_attr="bins_count",
    )

    painter.setPen(Qt.PenStyle.NoPen)
    for i in range(n):
        v = draw_values[i] if i < len(draw_values) else 0.0
        if v <= 0:
            continue
        x, cur_w = resolve_discrete_bar_geometry(
            i,
            step_x=step_x,
            bar_w=bar_w,
            slots=slots,
            margin_left=margin_left,
        )
        ratio_for_height = draw_ratios[i] if i < len(draw_ratios) else (v / max(1.0, widget.max_val))
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

    if not getattr(widget, "cumulative_visible", True):
        return
    n_bins = n
    if n_bins <= 0:
        return

    old_bins = int(widget._transition_old_bins_count or 0)
    new_bins = int(widget._transition_new_bins_count or 0)
    count_changed = widget._data_transition_active and old_bins > 0 and new_bins > 0 and old_bins != new_bins
    line_bins = new_bins if count_changed else n_bins

    if widget._data_transition_active and widget._transition_align_right and (not count_changed):
        x_positions = widget.interpolate_line_x_positions(
            widget._transition_old_bins_count,
            widget._transition_new_bins_count,
            t,
            margin_left,
            plot_w,
            align_right=True,
        )
    else:
        x_positions = build_default_line_x_positions(margin_left, plot_w, line_bins)

    if widget._data_transition_active:
        line_t = t
        if count_changed and line_t >= 0.98:
            line_t = 1.0
        old_vals = [float(v or 0.0) for v in (widget._transition_old_values or [])]
        new_vals = [float(v or 0.0) for v in (widget._transition_new_values or [])]
        sample_n = max(1, int(line_bins))

        old_curve = resample_discrete_series(normalized_running_total(old_vals), sample_n)
        new_curve = resample_discrete_series(normalized_running_total(new_vals), sample_n)
        cumulative_draw_values = [widget.interpolate_scalar(old_curve[i], new_curve[i], line_t) for i in range(sample_n)]
        line_total = 1.0
    else:
        cumulative_draw_values = build_running_total_series(draw_values)
        line_total = max(1.0, float(sum(draw_values) if draw_values else 0.0))

    if len(cumulative_draw_values) != len(x_positions):
        cumulative_draw_values = resample_discrete_series(cumulative_draw_values, len(x_positions))

    points = build_cumulative_points(
        x_positions,
        cumulative_draw_values,
        margin_top=margin_top,
        plot_h=plot_h,
        line_total=line_total,
    )
    cum_path, fill_path = build_cumulative_paths(points, margin_top=margin_top, plot_h=plot_h)
    if not cum_path or not fill_path:
        return

    painter.save()
    painter.setClipRect(QRectF(margin_left, margin_top - 2.0, plot_w, plot_h + 2.0))
    draw_cumulative_line_and_area(painter, cum_path, fill_path, widget=widget)
    painter.restore()


def paint_event_impl(widget, event):
    if not widget.data_list and not widget._data_transition_active:
        return

    painter = QPainter(widget)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    w = widget.width()
    h = widget.height()

    state = prepare_discrete_paint_state(
        widget,
        painter,
        t=widget.get_progress(),
        base_count_attr="_display_bins_count",
        anim_count_attr="_anim_bins_count",
        transition_count_attr="bins_count",
    )
    t = state["t"]
    draw_values = state["draw_values"]
    axis_max = state["axis_max"]
    margin_left = state["margin_left"]
    margin_right = state["margin_right"]
    margin_top = state["margin_top"]
    margin_bottom = state["margin_bottom"]
    plot_w = state["plot_w"]
    plot_h = state["plot_h"]

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
        max_cumulative=(int(sum(draw_values)) if getattr(widget, "show_cumulative_axis", True) else None),
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
            margin_left=margin_left,
            margin_bottom=margin_bottom,
            draw_values=draw_values,
        )
    else:
        widget.draw_extras(painter, plot_w, plot_h, margin_left, margin_top, margin_bottom, w, h)

    finalize_discrete_transition_state(widget, t=t, count_attr="bins_count")


def draw_extras_impl(widget, painter, plot_w, plot_h, margin_left, margin_top, margin_bottom, w, h):
    if widget.data_list:
        painter.setPen(get_theme_colors(widget).get("text_secondary", QColor("#888888")))
        font = painter.font()
        font.setPixelSize(9)
        painter.setFont(font)

        bs = max(1, int(getattr(widget, "_display_bin_size", 1) or 1))
        n_bins = int(getattr(widget, "_anim_bins_count", widget._display_bins_count) or 0)
        if n_bins <= 0:
            n_bins = int(getattr(widget, "_display_bins_count", 0) or 0)
        if n_bins <= 0:
            return
        step_x = plot_w / n_bins if n_bins > 0 else plot_w
        interval = max(1, n_bins // 5)

        for i in range(0, n_bins, interval):
            day = i * bs + (1 if bs <= 1 else 0)
            x = margin_left + (i * step_x) + (step_x / 2)
            t_rect = QRectF(x - 20, h - margin_bottom + 5, 40, 15)
            painter.drawText(t_rect, Qt.AlignmentFlag.AlignCenter, f"{day}d")

    if not widget.show_stats:
        return
    return draw_chart_bottom_stats(
        widget,
        painter,
        plot_w,
        h,
        margin_left,
        margin_bottom,
        require_positive_total=True,
    )
