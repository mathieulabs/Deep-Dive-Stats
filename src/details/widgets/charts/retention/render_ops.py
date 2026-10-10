# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from .bars import draw_review_bars
from .series import SERIES_KEYS
from .smooth import build_paths, control_points, tangents
from ..common.cache_dpr import cache_dpr, cache_surface, draw_cache, stale_cache
from aqt.qt import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPointF, Qt

from ....animations.easing import bezier01, early_fade
from ...chart_utils import ChartGeometry, get_theme_colors
from ...chart_utils.drawing import (
    stroke_average_line,
    draw_grid_and_axes,
    draw_right_axis_labels,
    draw_wrapped_bottom_stats,
    draw_x_axis_labels,
    get_hover_guide_pen,
    get_hover_marker_outline_color,
)
from ...chart_utils.drawing import chart_axes_style
from ..common.cache_keys import theme_color_token as _theme_color_token
from ....logic.logger import log_swallowed


def _dense_keep_indices(values, x_step):
    """Indices worth drawing when points are denser than one per pixel.

    Keeps the min and max of every 2px column plus the ends of each run.
    """
    if x_step <= 0 or x_step >= 0.5 or len(values) < 400:
        return None
    keep = set()
    col = None
    lo = hi = run_first = run_last = None
    for i, v in enumerate(values):
        if v is None:
            if col is not None:
                keep.update((lo, hi, run_first, run_last))
            col = lo = hi = run_first = run_last = None
            continue
        c = int(i * x_step / 2.0)
        if c != col:
            if col is not None:
                keep.update((lo, hi))
            col = c
            lo = hi = i
        else:
            if v < values[lo]:
                lo = i
            if v > values[hi]:
                hi = i
        if run_first is None:
            run_first = i
        run_last = i
    if col is not None:
        keep.update((lo, hi, run_first, run_last))
    return keep


def _draw_cached_scaffold(widget, painter, *, width, height, margin_left, margin_top, margin_right, margin_bottom, max_val, min_val=0):
    theme = get_theme_colors(widget)
    cache_key = (
        int(width),
        int(height),
        int(margin_left),
        int(margin_top),
        int(margin_right),
        int(margin_bottom),
        round(float(max_val), 2),
        round(float(min_val), 2),
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
        scaffold_painter = QPainter(px)
        try:
            scaffold_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            draw_grid_and_axes(
                scaffold_painter,
                width,
                height,
                margin_left,
                margin_top,
                margin_right,
                margin_bottom,
                max_val,
                widget=widget,
                min_val=min_val,
            )
        finally:
            scaffold_painter.end()
        widget._scaffold_cache_key = cache_key
        widget._scaffold_cache_pixmap = px
        pixmap = px

    if pixmap is not None:
        draw_cache(painter, pixmap)


def _draw_cached_chrome(
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
    plot_h,
    labels,
    stats,
    max_cum,
    min_val=0,
    max_val=100,
):
    theme = get_theme_colors(widget)
    avg_entries = []
    for key in SERIES_KEYS:
        y_avg = widget._get_series_avg_y(key, margin_top, plot_h, max_val, min_val=min_val)
        alpha_factor = widget._get_series_avg_alpha(key)
        avg_entries.append(
            (
                key,
                None if y_avg is None else round(float(y_avg), 3),
                round(float(alpha_factor or 0.0), 4),
                bool(widget.visible_series.get(key, False)),
                bool(widget.hover_avgs.get(key, False)),
            )
        )

    cache_key = (
        int(width),
        int(height),
        int(margin_left),
        int(margin_top),
        int(margin_right),
        int(margin_bottom),
        int(round(float(plot_w))),
        int(round(float(plot_h))),
        tuple(str(x) for x in (labels or [])),
        tuple(str(x) for x in (stats or [])),
        tuple(avg_entries),
        bool(getattr(widget, "avg_visible", True)),
        bool(getattr(widget, "show_stats", False)),
        bool(getattr(widget, "cumulative_visible", False)),
        int(round(float(max_cum or 0.0))),
        round(float(min_val), 2),
        round(float(max_val), 2),
        _theme_color_token(theme.get("text")),
        _theme_color_token(theme.get("grid")),
        chart_axes_style(widget),  # Settings > Chart Style: grid / quiet axes
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
        chrome_painter = QPainter(px)
        try:
            chrome_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            if labels and any(labels):
                draw_x_axis_labels(
                    chrome_painter,
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

            if bool(getattr(widget, "show_stats", False)):
                draw_wrapped_bottom_stats(
                    chrome_painter,
                    stats,
                    plot_w=plot_w,
                    height=height,
                    margin_left=margin_left,
                    margin_bottom=margin_bottom,
                    widget=widget,
                )

            if getattr(widget, "avg_visible", True):
                for key in SERIES_KEYS:
                    y_avg = widget._get_series_avg_y(key, margin_top, plot_h, max_val, min_val=min_val)
                    if y_avg is None:
                        continue
                    alpha_factor = max(0.0, min(1.0, float(widget._get_series_avg_alpha(key))))
                    if alpha_factor <= 0.001:
                        continue
                    stroke_average_line(
                        chrome_painter, margin_left, width - margin_right, y_avg,
                        QColor(widget._get_series_color(key, widget)),
                        widget=widget,
                        hovered=bool(widget.hover_avgs.get(key, False)),
                        alpha_factor=alpha_factor,
                    )

            if bool(getattr(widget, "cumulative_visible", False)) and max_cum > 0:
                draw_right_axis_labels(
                    chrome_painter,
                    width,
                    height,
                    margin_right,
                    margin_top,
                    margin_bottom,
                    int(max_cum),
                    widget=widget,
                )
        finally:
            chrome_painter.end()
        widget._chrome_cache_key = cache_key
        widget._chrome_cache_pixmap = px
        pixmap = px

    if pixmap is not None:
        draw_cache(painter, pixmap)


def draw_series_transition_impl(widget, painter, margin_left, margin_top, plot_w, plot_h, max_val, min_val=0):
    sample_count = int(widget._data_transition_sample_count)
    if sample_count < 2:
        return

    p = max(0.0, min(1.0, float(widget._progress)))
    x_step = plot_w / (sample_count - 1) if sample_count > 1 else 0.0
    base_y = margin_top + plot_h
    val_range = max(float(max_val) - float(min_val), 0.001)

    for series_key in SERIES_KEYS:
        if not widget.visible_series.get(series_key, False):
            continue
        old_vals = widget._data_transition_old_series.get(series_key, [])
        new_vals = widget._data_transition_new_series.get(series_key, [])
        if not old_vals and not new_vals:
            continue

        color = QColor(widget._get_series_color(series_key, widget))
        is_highlighted = widget.legend_hover_series == series_key
        is_dimmed = (widget.legend_hover_series is not None and series_key != widget.legend_hover_series)
        transition_cache = (widget._data_transition_render_cache or {}).get(series_key, {})
        old_filled = transition_cache.get("old_filled")
        new_filled = transition_cache.get("new_filled")
        old_mask = transition_cache.get("old_mask")
        new_mask = transition_cache.get("new_mask")
        segment_meta = transition_cache.get("segment_meta") or []
        point_meta = transition_cache.get("point_meta") or []
        has_presence = bool(transition_cache.get("has_presence", False))
        if old_filled is None or new_filled is None or old_mask is None or new_mask is None:
            continue
        if not has_presence:
            continue

        line_width = 2.0 if is_highlighted else (1.0 if is_dimmed else 1.5)
        opacity_f = getattr(widget, "chart_opacity_pct", 100) / 100.0
        base_alpha = int((255 if not is_dimmed else 60) * opacity_f)
        fill_top_base = int((40 if not is_dimmed else 25) * opacity_f)
        points = []
        presence = []

        for i in range(sample_count):
            ov = old_filled[i]
            nv = new_filled[i]
            val = ov + ((nv - ov) * p)
            pres = (old_mask[i] * (1.0 - p)) + (new_mask[i] * p)
            x = margin_left + (i * x_step)
            y = margin_top + plot_h - ((val - min_val) / val_range * plot_h)
            points.append(QPointF(x, y))
            presence.append(pres)

        stride = max(1, int(1.0 / x_step)) if x_step > 0 else 1
        slopes = tangents(points) if (stride == 1 and getattr(widget, "rounded", False)) else None
        for i in range(0, sample_count - 1, stride):
            j = min(i + stride, sample_count - 1)
            if i < len(segment_meta) and not segment_meta[i].get("candidate", False):
                continue
            seg_presence = min(presence[i], presence[j])
            if seg_presence <= 0.001:
                continue

            edge_fade = bool(i < len(segment_meta) and segment_meta[i].get("edge_fade", False))
            alpha_scale = (
                bezier01(early_fade(seg_presence, 0.22), 0.0, 0.2)
                if edge_fade
                else max(0.0, min(1.0, seg_presence))
            )

            p1 = points[i]
            p2 = points[j]
            draw_color = QColor(color)
            draw_color.setAlpha(int(base_alpha * alpha_scale))
            gradient = QLinearGradient(0, margin_top, 0, margin_top + plot_h)
            c_top = QColor(draw_color)
            c_top.setAlpha(int(fill_top_base * alpha_scale))
            c_bottom = QColor(draw_color)
            c_bottom.setAlpha(0)
            gradient.setColorAt(0, c_top)
            gradient.setColorAt(1, c_bottom)

            area = QPainterPath()
            area.moveTo(p1.x(), base_y)
            area.lineTo(p1)
            if slopes is not None:
                c1, c2 = control_points(p1, p2, slopes[i], slopes[j])
                area.cubicTo(c1, c2, p2)
            else:
                area.lineTo(p2)
            area.lineTo(p2.x(), base_y)
            area.closeSubpath()
            painter.fillPath(area, gradient)

            pen = QPen(draw_color, line_width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            if slopes is not None:
                seg = QPainterPath(p1)
                seg.cubicTo(c1, c2, p2)
                painter.strokePath(seg, pen)
            else:
                painter.drawLine(p1, p2)

        marker_size = 4.0 if is_highlighted else 3.0
        marker_radius = marker_size / 2.0
        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(sample_count):
            meta = point_meta[i] if i < len(point_meta) else None
            if meta is not None and not meta.get("candidate", False):
                continue
            point_presence = presence[i]
            if point_presence <= 0.001:
                continue
            left_link = min(presence[i - 1], point_presence) if i > 0 else 0.0
            right_link = min(point_presence, presence[i + 1]) if i < sample_count - 1 else 0.0
            if left_link > 0.01 or right_link > 0.01:
                continue

            appears_from_empty = bool(meta and meta.get("appears_from_empty", False))
            fades_to_empty = bool(meta and meta.get("fades_to_empty", False))
            edge_point = bool(meta and meta.get("edge_point", False))
            alpha_presence = (
                bezier01(early_fade(point_presence, 0.22), 0.0, 0.2)
                if (fades_to_empty and edge_point)
                else bezier01(point_presence, 0.05, 0.35)
                if fades_to_empty
                else point_presence
            )
            marker_center = points[i]
            if appears_from_empty:
                ny = margin_top + plot_h - ((new_filled[i] - min_val) / val_range * plot_h)
                marker_center = QPointF(marker_center.x(), ny)
            elif fades_to_empty:
                oy = margin_top + plot_h - ((old_filled[i] - min_val) / val_range * plot_h)
                marker_center = QPointF(marker_center.x(), oy)

            marker_color = QColor(color)
            marker_color.setAlpha(int(base_alpha * max(0.0, min(1.0, alpha_presence))))
            painter.setBrush(marker_color)
            painter.drawEllipse(marker_center, marker_radius, marker_radius)


def paint_event_impl(widget, event):
    display_data = widget._get_display_data()
    if not display_data:
        return

    painter = QPainter(widget)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    w = widget.width()
    h = widget.height()

    if getattr(widget, "fit_to_data", False):
        if widget._data_transition_active:
            p = max(0.0, min(1.0, float(getattr(widget, "_progress", 1.0))))
            old_min, old_max = getattr(widget, "_data_transition_old_range", (0.0, 100.0))
            new_min, new_max = getattr(widget, "_data_transition_new_range", (0.0, 100.0))
            min_val = old_min + (new_min - old_min) * p
            max_val = old_max + (new_max - old_max) * p
        else:
            min_val, max_val = widget.get_data_range()
    else:
        min_val, max_val = 0.0, 100.0
    val_range = max(float(max_val) - float(min_val), 0.001)
    margin_left = ChartGeometry.calculate_dynamic_left_margin(painter.fontMetrics(), max_val, min_val=min_val)
    margin_right = widget._get_margin_right(painter.fontMetrics())
    plot_w = w - margin_left - margin_right

    show_stats = getattr(widget, "show_stats", False)
    if show_stats:
        stats = widget.get_stats_text()
        margin_bottom = ChartGeometry.calculate_stats_margin(stats, plot_w, painter.fontMetrics())
    else:
        margin_bottom = ChartGeometry.MARGIN_BOTTOM

    margin_top = ChartGeometry.MARGIN_TOP
    plot_h = h - margin_bottom - margin_top
    t_colors = get_theme_colors(widget)
    is_dark = bool(t_colors.get("is_dark"))

    _draw_cached_scaffold(
        widget,
        painter,
        width=w,
        height=h,
        margin_left=margin_left,
        margin_top=margin_top,
        margin_right=margin_right,
        margin_bottom=margin_bottom,
        max_val=max_val,
        min_val=min_val,
    )


    labels = []
    n = widget._get_display_n()
    for key in SERIES_KEYS:
        if key in display_data and display_data[key]:
            for item in display_data[key]:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    labels.append(str(item[0]).split(" - ")[0])
                else:
                    labels.append("")
            break

    axis_old_labels = widget._data_transition_old_labels if widget._data_transition_active else None
    axis_progress = widget.get_progress() if widget._data_transition_active else 1.0
    max_cum = 0.0
    if getattr(widget, "cumulative_visible", False):
        for item in (display_data.get("all", []) or []):
            if not isinstance(item, (list, tuple)) or len(item) < 3:
                continue
            payload = item[2]
            if not isinstance(payload, (list, tuple)) or len(payload) < 2:
                continue
            try:
                max_cum += float(payload[1] or 0.0)
            except Exception:
                log_swallowed()

    use_cached_chrome = (
        (not widget._data_transition_active)
        and float(getattr(widget, "_progress", 1.0)) < 0.999
        and widget.legend_hover_series is None
        and int(getattr(widget, "hover_index", -1)) == -1
        and not any(bool(v) for v in (getattr(widget, "hover_avgs", {}) or {}).values())
    )
    if use_cached_chrome:
        _draw_cached_chrome(
            widget,
            painter,
            width=w,
            height=h,
            margin_left=margin_left,
            margin_top=margin_top,
            margin_right=margin_right,
            margin_bottom=margin_bottom,
            plot_w=plot_w,
            plot_h=plot_h,
            labels=labels,
            stats=stats if show_stats else [],
            max_cum=max_cum,
            min_val=min_val,
            max_val=max_val,
        )
    else:
        if labels and any(labels):
            draw_x_axis_labels(
                painter,
                labels,
                w,
                h,
                margin_left,
                margin_right,
                margin_bottom,
                old_labels=axis_old_labels,
                progress=axis_progress,
                widget=widget,
            )

        widget.draw_bottom_stats(painter, plot_w, h, margin_left, margin_bottom)

        if getattr(widget, "avg_visible", True):
            for key in SERIES_KEYS:
                y_avg = widget._get_series_avg_y(key, margin_top, plot_h, max_val, min_val=min_val)
                if y_avg is None:
                    continue
                alpha_factor = max(0.0, min(1.0, float(widget._get_series_avg_alpha(key))))
                if alpha_factor <= 0.001:
                    continue
                stroke_average_line(
                    painter, margin_left, w - margin_right, y_avg,
                    QColor(widget._get_series_color(key, widget)),
                    widget=widget,
                    hovered=bool(widget.hover_avgs[key]),
                    alpha_factor=alpha_factor,
                )

    if n == 0:
        return

    painter.save()
    if not widget._data_transition_active:
        clip_width = int(w * widget._progress)
        painter.setClipRect(0, 0, clip_width, h)

    x_step = plot_w / (n - 1) if n > 1 else 0
    draw_review_bars(widget, painter, display_data, n, margin_left, margin_top, plot_w, plot_h, x_step, is_dark)
    use_series_transition = (
        widget._data_transition_active
        and widget._data_transition_sample_count >= 2
        and bool(widget._data_transition_old_series)
        and bool(widget._data_transition_new_series)
    )
    if use_series_transition:
        widget._draw_series_transition(painter, margin_left, margin_top, plot_w, plot_h, max_val, min_val=min_val)
    else:
        for series_key in SERIES_KEYS:
            if not widget.visible_series.get(series_key, False):
                continue
            if series_key not in display_data or not display_data[series_key]:
                continue
            series_data = display_data[series_key]
            color = QColor(widget._get_series_color(series_key, widget))
            is_highlighted = (widget.legend_hover_series == series_key)
            is_dimmed = (widget.legend_hover_series is not None and series_key != widget.legend_hover_series)
            opacity_f = getattr(widget, "chart_opacity_pct", 100) / 100.0
            if is_dimmed:
                color.setAlpha(int(60 * opacity_f))
            elif widget.legend_hover_series is not None:
                color.setAlpha(int(255 * opacity_f))

            cached = widget._path_cache.get(series_key)
            if cached:
                path, area_path, isolated_points = cached
            else:
                values = []
                for item in series_data:
                    if isinstance(item, (list, tuple)):
                        values.append(item[1])
                    else:
                        values.append(item)
                path = QPainterPath()
                area_path = QPainterPath()
                isolated_points = []
                last_pt = None
                runs = []
                keep = _dense_keep_indices(values, x_step)
                for i, val in enumerate(values):
                    x = margin_left + (i * x_step)
                    if keep is not None and val is not None and i not in keep:
                        continue
                    if val is not None:
                        y = margin_top + plot_h - ((val - min_val) / val_range * plot_h)
                        p = QPointF(x, y)
                        if last_pt is None:
                            runs.append([])
                            path.moveTo(p)
                            area_path.moveTo(x, margin_top + plot_h)
                            area_path.lineTo(p)
                        else:
                            path.lineTo(p)
                            area_path.lineTo(p)
                        last_pt = p
                        runs[-1].append(p)
                        has_left = (i > 0 and values[i - 1] is not None)
                        has_right = (i < len(values) - 1 and values[i + 1] is not None)
                        if not has_left and not has_right:
                            isolated_points.append(p)
                    else:
                        if last_pt is not None:
                            area_path.lineTo(last_pt.x(), margin_top + plot_h)
                        last_pt = None
                if last_pt is not None:
                    area_path.lineTo(last_pt.x(), margin_top + plot_h)
                if getattr(widget, "rounded", False):
                    path, area_path = build_paths(runs, margin_top + plot_h)
                widget._path_cache[series_key] = (path, area_path, isolated_points)

            if not area_path.isEmpty():
                gradient = QLinearGradient(0, margin_top, 0, margin_top + plot_h)
                c_top = QColor(color)
                c_top.setAlpha(int((25 if is_dimmed else 40) * opacity_f))
                c_bottom = QColor(color)
                c_bottom.setAlpha(0)
                gradient.setColorAt(0, c_top)
                gradient.setColorAt(1, c_bottom)
                painter.fillPath(area_path, gradient)

            line_width = 2.0 if is_highlighted else (1.0 if is_dimmed else 1.5)
            pen = QPen(color, line_width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.strokePath(path, pen)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            marker_size = 4.0 if is_highlighted else 3.0
            for pt in isolated_points:
                painter.drawEllipse(pt, marker_size / 2, marker_size / 2)

    painter.restore()

    if widget.hover_index != -1 and 0 <= widget.hover_index < n:
        x = margin_left + (widget.hover_index * x_step) if n > 1 else margin_left
        painter.setPen(get_hover_guide_pen(widget, width=1))
        painter.drawLine(QPointF(x, margin_top), QPointF(x, margin_top + plot_h))
        for k in SERIES_KEYS:
            if widget.visible_series.get(k, False) and k in display_data:
                series_data = display_data[k]
                if widget.hover_index >= len(series_data):
                    continue
                item = series_data[widget.hover_index]
                val = item[1] if isinstance(item, (list, tuple)) else item
                if val is None:
                    continue
                y = margin_top + plot_h - ((val - min_val) / val_range * plot_h)
                color = QColor(widget._get_series_color(k, widget))
                painter.setBrush(color)
                outline_col = get_hover_marker_outline_color(widget)
                outline_col.setAlpha(230 if is_dark else 210)
                painter.setPen(QPen(outline_col, 1.5))
                painter.drawEllipse(QPointF(x, y), 4, 4)

    if getattr(widget, "cumulative_visible", False):
        if max_cum > 0 and not use_cached_chrome:
            draw_right_axis_labels(
                painter,
                w,
                h,
                margin_right,
                margin_top,
                margin_bottom,
                int(max_cum),
                widget=widget,
            )

    widget.draw_selection_overlay(painter, margin_left, margin_top, plot_w, plot_h)


def draw_bottom_stats_impl(widget, painter, plot_w, h, margin_left, margin_bottom):
    if not getattr(widget, "show_stats", False):
        return
    stats = widget.get_stats_text()
    draw_wrapped_bottom_stats(
        painter,
        stats,
        plot_w=plot_w,
        height=h,
        margin_left=margin_left,
        margin_bottom=margin_bottom,
        widget=widget,
    )
