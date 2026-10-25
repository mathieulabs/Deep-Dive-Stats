# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Cached scaffold and chrome painting shared by the Activity and Breakdown charts."""

from ....chart_utils import get_theme_colors
from ....chart_utils.drawing import chart_style, chart_axes_style, draw_grid_and_axes, draw_right_axis_labels, draw_x_axis_labels, stroke_average_line
from ..cache_dpr import cache_dpr, cache_surface, draw_cache, stale_cache
from ..cache_keys import theme_color_token as _theme_color_token
from aqt.qt import QPainter, Qt


def draw_cached_scaffold(widget, painter, *, width, height, margin_left, margin_top, margin_right, margin_bottom, left_axis_max):
    theme = get_theme_colors(widget)
    cache_key = (
        int(width),
        int(height),
        int(margin_left),
        int(margin_top),
        int(margin_right),
        int(margin_bottom),
        float(left_axis_max or 0.0),  # exact: nearly equal maxima can still give other labels
        str(getattr(widget, "value_mode", "")),
        str(getattr(widget, "chart_type", "")),
        bool(getattr(widget, "cumulative_visible", False)),
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
                left_axis_max,
                value_formatter=widget._axis_value_formatter if widget._is_time_mode() else None,
                widget=widget,
            )
        finally:
            sp.end()
        widget._scaffold_cache_key = cache_key
        widget._scaffold_cache_pixmap = px
        pixmap = px

    if pixmap is not None:
        draw_cache(painter, pixmap)


def draw_cached_chrome(
    widget,
    painter,
    *,
    width,
    height,
    margin_left,
    margin_top,
    margin_right,
    margin_bottom,
    plot_w,
    labels,
    stats,
    avg_y,
    right_axis_max,
):
    theme = get_theme_colors(widget)
    cache_key = (
        chart_style(widget),  # line opacity setting (Total / Average lines)
        int(width),
        int(height),
        int(margin_left),
        int(margin_top),
        int(margin_right),
        int(margin_bottom),
        int(round(float(plot_w or 0.0))),
        tuple(str(x) for x in (labels or [])),
        tuple(str(x) for x in (stats or [])),
        None if avg_y is None else int(round(float(avg_y))),
        None if right_axis_max is None else int(round(float(right_axis_max or 0.0))),
        bool(getattr(widget, "avg_visible", True)),
        bool(getattr(widget, "hover_avg", False)),
        bool(getattr(widget, "show_stats", False)),
        bool(getattr(widget, "cumulative_visible", False)),
        str(getattr(widget, "value_mode", "")),
        str(getattr(widget, "chart_type", "")),
        _theme_color_token(theme.get("text")),
        _theme_color_token(theme.get("grid")),
        chart_axes_style(widget),  # Settings > Chart Style: grid / quiet axes
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
            if labels and any(labels):
                draw_x_axis_labels(
                    cp,
                    labels,
                    width,
                    height,
                    margin_left,
                    margin_right,
                    margin_bottom,
                    old_labels=None,
                    progress=1.0,
                    widget=widget,
                )
            widget.draw_bottom_stats(cp, plot_w, height, margin_left, margin_bottom)
            if avg_y is not None:
                pal = get_theme_colors(widget)
                base = pal.get("total_line") or ("#ffffff" if bool(pal.get("is_dark")) else "#000000")
                stroke_average_line(
                    cp, margin_left, width - margin_right, int(avg_y), base,
                    widget=widget, hovered=bool(getattr(widget, "hover_avg", False)),
                )
            if right_axis_max is not None:
                draw_right_axis_labels(
                    cp,
                    width,
                    height,
                    margin_right,
                    margin_top,
                    margin_bottom,
                    right_axis_max,
                    value_formatter=widget._axis_value_formatter if widget._is_time_mode() else None,
                    widget=widget,
                )
        finally:
            cp.end()
        widget._chrome_cache_key = cache_key
        widget._chrome_cache_pixmap = px
        pixmap = px

    if pixmap is not None:
        draw_cache(painter, pixmap)


def mode_switch_blend(widget, t):
    """(old_formatter, new_formatter, blend) while a Reviews <-> Time switch glides, else None.

    The axis numbers of the two modes are not comparable (327 reviews vs 24 minutes), so
    during the switch each mode keeps its own labels and they cross-fade instead of the
    number counting through the wrong unit."""
    if not getattr(widget, "_data_transition_active", False):
        return None
    old_mode = str(getattr(widget, "_transition_old_value_mode", widget.value_mode) or "").lower()
    new_mode = str(getattr(widget, "_transition_new_value_mode", widget.value_mode) or "").lower()
    if old_mode == new_mode:
        return None
    from .ops import transition_margin_formatters

    old_fmt, new_fmt = transition_margin_formatters(widget)
    tt = max(0.0, min(1.0, float(t)))
    return old_fmt, new_fmt, tt * tt * (3.0 - 2.0 * tt)


def _blend_layers(blend, old_max, new_max):
    """Old numbers fade out, then the new ones fade in, so two units never overlap."""
    old_fmt, new_fmt, e = blend
    old_alpha = max(0.0, min(1.0, 1.0 - e / 0.45))
    new_alpha = max(0.0, min(1.0, (e - 0.55) / 0.45))
    return ((old_fmt, old_max, old_alpha), (new_fmt, new_max, new_alpha))


def draw_blended_scaffold(widget, painter, blend, *, width, height, margin_left, margin_top, margin_right, margin_bottom, old_max, new_max):
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    # The grid lines stay put; only the numbers swap.
    draw_grid_and_axes(
        painter,
        width,
        height,
        margin_left,
        margin_top,
        margin_right,
        margin_bottom,
        new_max,
        widget=widget,
        draw_labels=False,
    )
    painter.restore()
    for fmt, axis_max, alpha in _blend_layers(blend, old_max, new_max):
        if alpha <= 0.004:
            continue
        painter.save()
        painter.setOpacity(painter.opacity() * alpha)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        draw_grid_and_axes(
            painter,
            width,
            height,
            margin_left,
            margin_top,
            margin_right,
            margin_bottom,
            axis_max,
            value_formatter=fmt,
            widget=widget,
            draw_lines=False,
        )
        painter.restore()


def draw_blended_right_labels(widget, painter, blend, *, width, height, margin_right, margin_top, margin_bottom, old_max, new_max):
    for fmt, axis_max, alpha in _blend_layers(blend, old_max, new_max):
        if alpha <= 0.004:
            continue
        painter.save()
        painter.setOpacity(painter.opacity() * alpha)
        draw_right_axis_labels(
            painter,
            width,
            height,
            margin_right,
            margin_top,
            margin_bottom,
            axis_max,
            value_formatter=fmt,
            widget=widget,
        )
        painter.restore()
