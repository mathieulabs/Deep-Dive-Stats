# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from aqt.qt import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPointF, QRectF, Qt
from ..common.smooth_line import add_smooth_line

from ...chart_utils import ChartGeometry, get_theme_colors, is_night_mode
from ...chart_utils.drawing import (
    stroke_average_line,
    draw_bar_rect,
    draw_cumulative_line_and_area,
    draw_right_axis_labels,
    draw_x_axis_labels,
    get_hover_guide_pen,
    get_hover_marker_outline_color,
)
from ..common.metric import (
    calculate_margin_pair,
    calculate_stats_margin,
    compute_transition_presence,
    draw_bottom_stats_impl,
    interpolate_axis_max,
    interpolate_margin_pair,
    transition_margin_formatters,
    split_transition_labels,
)
from ..common.metric.chrome import (
    draw_blended_right_labels,
    draw_blended_scaffold,
    draw_cached_chrome as _draw_cached_chrome,
    draw_cached_scaffold as _draw_cached_scaffold,
    mode_switch_blend,
)
from ..common.zoom_view import (
    bar_slot,
    cumulative_edge_blend,
    cumulative_points,
    dense_bar_ratio,
    get_zoom_view,
    zoom_view_bar,
    zoom_view_margins,
)


def _decimate_points(points, plot_w, col_px=1):
    """Keep min/max per pixel column so unbinned series stay cheap to stroke."""
    n = len(points)
    cols = max(1, int(plot_w / col_px))
    if n <= cols * 2:
        return points
    out = [points[0]]
    i = 1
    last = n - 1
    while i < last:
        bucket = int(points[i].x() / col_px)
        j = i
        lo = hi = points[i]
        while j < last and int(points[j].x() / col_px) == bucket:
            pt = points[j]
            if pt.y() < lo.y():
                lo = pt
            if pt.y() > hi.y():
                hi = pt
            j += 1
        if lo is hi:
            out.append(lo)
        elif lo.x() <= hi.x():
            out.extend((lo, hi))
        else:
            out.extend((hi, lo))
        i = j
    out.append(points[last])
    return out


def paint_event_impl(widget, event):
    if not widget.data:
        return

    painter = QPainter(widget)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    w = widget.width()
    h = widget.height()

    t_colors = get_theme_colors(widget)
    is_dark = bool(t_colors.get("is_dark"))

    margin_top = ChartGeometry.MARGIN_TOP
    margin_bottom = ChartGeometry.MARGIN_BOTTOM

    values = widget._get_values()
    labels = widget._get_labels()
    axis_old_labels = None
    max_val = widget._get_max_val()
    t = widget.get_progress()
    if widget._data_transition_active and t >= 0.999:
        target_vals = [d[1] if isinstance(d, (list, tuple)) else d for d in (widget._transition_new_data or [])]
        target_max = max(target_vals) if target_vals else 0.0
        widget._trace_activity_state(
            "transition_end",
            progress=round(float(t), 3),
            target_len=len(target_vals),
            target_max=round(float(target_max), 3),
        )
        widget._finalize_data_transition()
        widget._invalidate_data_caches()
        t = 1.0
        values = widget._get_values()
        labels = widget._get_labels()
        max_val = widget._get_max_val()
    use_relative_transition = (
        widget.chart_type == "bar"
        and widget._relative_height_transition
        and widget._data_transition_active
        and widget._global_transition_mode is None
    )
    if widget._global_transition_mode == "from_empty":
        values = [d[1] if isinstance(d, (list, tuple)) else d for d in widget._transition_new_data]
        labels = [str(d[0]) if isinstance(d, (list, tuple)) else "" for d in widget._transition_new_data]
        max_val = max(values) if values else 1.0
    elif widget._global_transition_mode == "to_empty":
        values = [d[1] if isinstance(d, (list, tuple)) else d for d in widget._transition_old_data]
        labels = [str(d[0]) if isinstance(d, (list, tuple)) else "" for d in widget._transition_old_data]
        max_val = max(values) if values else 1.0
    elif use_relative_transition:
        values = widget._interpolate_relative_height_values(t)
        axis_old_labels, labels = split_transition_labels(
            widget._transition_old_data,
            widget._transition_new_data,
            label_getter=lambda item: item[0] if isinstance(item, (list, tuple)) else "",
        )
        max_val = 1.0
    elif widget._data_transition_active:
        old_values = [
            d[1] if isinstance(d, (list, tuple)) else d
            for d in widget._transition_old_data
        ]
        new_values = [
            d[1] if isinstance(d, (list, tuple)) else d
            for d in widget._transition_new_data
        ]
        if widget._transition_align_right:
            values = widget.interpolate_numeric_series(old_values, new_values, t, align_right=True)
        else:
            values = widget.interpolate_numeric_series(old_values, new_values, t)
        axis_old_labels, labels = split_transition_labels(
            widget._transition_old_data,
            widget._transition_new_data,
            label_getter=lambda item: item[0] if isinstance(item, (list, tuple)) else "",
        )
        old_max = max(old_values) if old_values else 1.0
        new_max = max(new_values) if new_values else 1.0
        max_val = max(1.0, old_max + ((new_max - old_max) * t))
    zv = get_zoom_view(widget) if widget.chart_type == "bar" else None
    if zv is not None:
        max_val = max(1e-9, float(zv["max"]))
    presence = compute_transition_presence(widget, t)
    draw_presence = presence if widget.chart_type == "bar" else 1.0
    fm = widget.fontMetrics()

    if widget._global_transition_mode is not None or widget._data_transition_active:
        old_values_for_margin = [
            d[1] if isinstance(d, (list, tuple)) else d
            for d in widget._transition_old_data
        ]
        new_values_for_margin = [
            d[1] if isinstance(d, (list, tuple)) else d
            for d in widget._transition_new_data
        ]
        # Format each side with its own mode so Reviews <-> Time glides instead of jumping.
        old_fmt, new_fmt = transition_margin_formatters(widget)
        margin_left, margin_right = interpolate_margin_pair(
            fm,
            old_values_for_margin,
            new_values_for_margin,
            t,
            getattr(widget, "cumulative_visible", False),
            old_formatter=old_fmt,
            new_formatter=new_fmt,
        )
    elif zv is not None:
        _cum_src = widget._get_cumulative() if getattr(widget, "cumulative_visible", False) else []
        margin_left, margin_right = zoom_view_margins(
            zv,
            fm,
            _cum_src,
            getattr(widget, "cumulative_visible", False),
            value_formatter=widget._axis_value_formatter if widget._is_time_mode() else None,
        )
    else:
        margin_left, margin_right = calculate_margin_pair(
            fm,
            values,
            getattr(widget, "cumulative_visible", False),
            value_formatter=widget._axis_value_formatter if widget._is_time_mode() else None,
        )

    plot_w = w - margin_left - margin_right

    margin_bottom = calculate_stats_margin(widget, painter, plot_w)

    plot_h = h - margin_bottom - margin_top

    cumulative_values = []
    max_cumulative = 1
    zv_cum_points = None
    if getattr(widget, "cumulative_visible", False):
        # Keep cumulative line stable during initial reveal; only morph/fade on
        # real data transitions (timespan / empty graph transitions).
        if widget._global_transition_mode == "from_empty":
            cumulative_presence = t
        elif widget._global_transition_mode == "to_empty":
            cumulative_presence = 1.0 - t
        else:
            cumulative_presence = 1.0
        if use_relative_transition:
            cumulative_values = widget._interpolate_relative_cumulative(t)
        elif widget._data_transition_active:
            cumulative_values = []
            run_sum = 0.0
            for v in values:
                run_sum += v
                cumulative_values.append(run_sum)
        else:
            cumulative_values = widget._get_cumulative()
        zv_cum_points = None
        if zv is not None and cumulative_values:
            zv_cum_points, _zv_top = cumulative_points(zv, cumulative_values, margin_left, plot_w)
            cumulative_values = [v for _x, v in zv_cum_points]
        if cumulative_presence != 1.0:
            cumulative_values = [v * cumulative_presence for v in cumulative_values]
        max_cumulative = cumulative_values[-1] if cumulative_values else 1
        if zv_cum_points is not None:
            max_cumulative = _zv_top
        if max_cumulative == 0: max_cumulative = 1

    left_axis_max = max_val
    _blend = None
    _left_ends = None
    if widget._global_transition_mode is not None or widget._data_transition_active:
        old_vals_for_axis = [
            d[1] if isinstance(d, (list, tuple)) else d
            for d in (widget._transition_old_data or [])
        ]
        new_vals_for_axis = [
            d[1] if isinstance(d, (list, tuple)) else d
            for d in (widget._transition_new_data or [])
        ]
        left_axis_max = interpolate_axis_max(old_vals_for_axis, new_vals_for_axis, t)
        if widget._global_transition_mode is None:
            _blend = mode_switch_blend(widget, t)
            if _blend is not None:
                _left_ends = (
                    interpolate_axis_max(old_vals_for_axis, new_vals_for_axis, 0.0),
                    interpolate_axis_max(old_vals_for_axis, new_vals_for_axis, 1.0),
                )

    if _blend is not None:
        draw_blended_scaffold(
            widget,
            painter,
            _blend,
            width=w,
            height=h,
            margin_left=margin_left,
            margin_top=margin_top,
            margin_right=margin_right,
            margin_bottom=margin_bottom,
            old_max=_left_ends[0],
            new_max=_left_ends[1],
        )
    else:
        _draw_cached_scaffold(
            widget,
            painter,
            width=w,
            height=h,
            margin_left=margin_left,
            margin_top=margin_top,
            margin_right=margin_right,
            margin_bottom=margin_bottom,
            left_axis_max=left_axis_max,
        )

    n = len(values)
    if n > 0:
        needs_clip = (
            widget.chart_type == "line"
            and (widget._progress < 0.999)
            and (not widget._data_transition_active)
            and (widget._global_transition_mode is None)
        )
        if needs_clip:
            painter.save()
            clip_width = (w * widget._progress)
            painter.setClipRect(0, 0, int(clip_width), h)

        x_step = plot_w / (n - 1) if n > 1 else 0

        if widget.chart_type == "line":
            use_cache = not widget._data_transition_active
            if (not use_cache) or widget._path_cache is None:
                path = QPainterPath()
                points = []
                for i, val in enumerate(values):
                    x = margin_left + (i * x_step)
                    y = margin_top + plot_h - (val / max_val * plot_h)
                    points.append(QPointF(x, y))

                points = _decimate_points(points, plot_w, 2 if widget._data_transition_active else 1)
                if points:
                    path.moveTo(points[0])
                    for p in points[1:]:
                        path.lineTo(p)

                area_path = QPainterPath(path)
                area_path.lineTo(points[-1].x(), margin_top + plot_h)
                area_path.lineTo(points[0].x(), margin_top + plot_h)
                area_path.closeSubpath()

                if use_cache:
                    widget._path_cache = path
                    widget._area_path_cache = area_path

            gradient = QLinearGradient(0, margin_top, 0, margin_top + plot_h)
            c_top = QColor(widget.color)
            c_top.setAlpha(150)
            c_bottom = QColor(widget.color)
            c_bottom.setAlpha(10)
            gradient.setColorAt(0, c_top)
            gradient.setColorAt(1, c_bottom)

            if use_cache:
                painter.fillPath(widget._area_path_cache, gradient)
            else:
                painter.fillPath(area_path, gradient)

            pen = QPen(widget.color, 2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            if use_cache:
                painter.strokePath(widget._path_cache, pen)
            else:
                painter.strokePath(path, pen)

        elif widget.chart_type == "bar":
            step_x = plot_w / n
            bar_x0 = margin_left
            if zv is not None:
                widget._zoom_view_plot = (margin_left, margin_top, plot_w, plot_h)
                bar_x0, step_x = bar_slot(zv, margin_left, plot_w)
                painter.save()
                painter.setClipRect(QRectF(margin_left, 0.0, plot_w, margin_top + plot_h))
            _wr = dense_bar_ratio(step_x, 0.9)
            bar_w = step_x * _wr
            bar_slots = None
            if widget._data_transition_active and widget._transition_align_right:
                bar_slots = widget.interpolate_bar_slots(
                    len(widget._transition_old_data),
                    len(widget._transition_new_data),
                    t,
                    margin_left,
                    plot_w,
                    align_right=True,
                    width_ratio=_wr,
                )

            # Height-based color interpolation (taller = darker), shared with Hourly and Added.
            _base = QColor(widget.color)
            _is_dark = is_night_mode(widget)
            _light_mul = 1.4 if _is_dark else 1.22
            _dark_mul = 0.7 if _is_dark else 0.68
            _l_max = min(255, int(_base.lightness() * _light_mul))
            _l_min = max(0, int(_base.lightness() * _dark_mul))

            _hue, _sat = _base.hslHue(), _base.hslSaturation()
            _alpha = int(getattr(widget, 'chart_opacity_pct', 100) * 2.55)
            _shade_max = float((zv.get("color_max") if zv is not None else None) or max_val)
            _colors = {}  # lightness -> colour (hundreds of bars share a few shades)
            painter.setPen(Qt.PenStyle.NoPen)
            for i, val in enumerate(values):
                if bar_slots and i < len(bar_slots):
                    center_x, slot_w = bar_slots[i]
                    x = center_x - (slot_w * 0.5)
                    draw_bar_w = slot_w
                else:
                    x = bar_x0 + (i * step_x) + (step_x - bar_w) / 2
                    draw_bar_w = bar_w
                    if zv is not None:
                        x, draw_bar_w = zoom_view_bar(zv, i, x, draw_bar_w, bar_x0, step_x)
                if zv is not None and (x > margin_left + plot_w or x + draw_bar_w < margin_left):
                    continue
                bar_h = (val / max_val) * plot_h * draw_presence
                y = margin_top + plot_h - bar_h

                ratio = min(1.0, val / _shade_max) if _shade_max > 0 else 0
                # ratio=1 => dark, ratio=0 => light
                current_l = int(_l_max - ((_l_max - _l_min) * ratio))
                c = _colors.get(current_l)
                if c is None:
                    c = QColor(_base)
                    c.setHsl(_hue, _sat, current_l)
                    c.setAlpha(_alpha)
                    _colors[current_l] = c

                if i == widget.hover_index:
                    c = c.lighter(130) if _is_dark else c.darker(115)
                    c.setAlpha(255)

                if draw_bar_w < 2.0:
                    # Hair-thin bar: a plain rectangle (what draw_bar_rect would draw), faster.
                    painter.fillRect(QRectF(x, y, draw_bar_w, bar_h), c)
                    continue
                painter.setBrush(c)
                draw_bar_rect(
                    painter, QRectF(x, y, draw_bar_w, bar_h),
                    radius=(zv.get("radius", 1.8) if zv is not None else 1.8), widget=widget,
                )

        if getattr(widget, "cumulative_visible", False) and cumulative_values:
            if zv_cum_points is not None:
                points = [QPointF(zv_cum_points[i][0], margin_top + plot_h - (val / max_cumulative * plot_h))
                          for i, val in enumerate(cumulative_values)]
                if points:
                    cum_path = QPainterPath()
                    cum_path.moveTo(points[0])
                    add_smooth_line(cum_path, points, edge_blend=cumulative_edge_blend(zv, len(points)))
                    fill_path = QPainterPath(cum_path)
                    fill_path.lineTo(points[-1].x(), margin_top + plot_h)
                    fill_path.lineTo(points[0].x(), margin_top + plot_h)
                    fill_path.closeSubpath()
                    draw_cumulative_line_and_area(painter, cum_path, fill_path, widget=widget)
            elif widget._data_transition_active:
                cum_path = QPainterPath()
                points = []
                n_cum = len(cumulative_values)
                x_positions = None
                if widget._transition_align_right:
                    x_positions = widget.interpolate_line_x_positions(
                        len(widget._transition_old_data),
                        len(widget._transition_new_data),
                        t,
                        margin_left,
                        plot_w,
                        align_right=True,
                    )
                if n_cum > 0:
                    step_x_cum = plot_w / (n_cum - 1) if n_cum > 1 else 0
                    for i, val in enumerate(cumulative_values):
                        if x_positions and i < len(x_positions):
                            x = x_positions[i]
                        else:
                            x = margin_left + (i * step_x_cum)
                        y = margin_top + plot_h - (val / max_cumulative * plot_h)
                        points.append(QPointF(x, y))
                    if points:
                        cum_path.moveTo(points[0])
                        add_smooth_line(cum_path, points)
                        fill_path = QPainterPath(cum_path)
                        fill_path.lineTo(points[-1].x(), margin_top + plot_h)
                        fill_path.lineTo(points[0].x(), margin_top + plot_h)
                        fill_path.closeSubpath()
                        draw_cumulative_line_and_area(painter, cum_path, fill_path, widget=widget)
            elif widget._cum_path_cache is None and zv_cum_points is None:
                cum_path = QPainterPath()
                points = []
                n_cum = len(cumulative_values)
                if n_cum > 0:
                    step_x_cum = plot_w / (n_cum - 1) if n_cum > 1 else 0

                    for i, val in enumerate(cumulative_values):
                        x = margin_left + (i * step_x_cum)
                        y = margin_top + plot_h - (val / max_cumulative * plot_h)
                        points.append(QPointF(x, y))

                    if points:
                        cum_path.moveTo(points[0])
                        add_smooth_line(cum_path, points)

                        fill_path = QPainterPath(cum_path)
                        fill_path.lineTo(points[-1].x(), margin_top + plot_h)
                        fill_path.lineTo(points[0].x(), margin_top + plot_h)
                        fill_path.closeSubpath()
                        widget._cum_path_cache = (cum_path, fill_path)

            if (not widget._data_transition_active) and zv_cum_points is None and widget._cum_path_cache:
                p_line, p_fill = widget._cum_path_cache
                draw_cumulative_line_and_area(painter, p_line, p_fill, widget=widget)
        if zv is not None and widget.chart_type == "bar":
            painter.restore()

        if needs_clip:
            painter.restore()

    avg_y = None
    avg_pen_target = None
    right_axis_max = None

    # Average line, drawn after the data so it sits on top
    if widget.avg_visible and values:
        def _avg_from_values(arr):
            if not arr:
                return 0.0
            if widget.avg_on_active_days:
                non_zeros = [v for v in arr if v > 0]
                return (sum(non_zeros) / len(non_zeros)) if non_zeros else 0.0
            return sum(arr) / len(arr)

        if widget._data_transition_active or widget._global_transition_mode is not None:
            old_vals = [
                d[1] if isinstance(d, (list, tuple)) else d
                for d in widget._transition_old_data
            ]
            new_vals = [
                d[1] if isinstance(d, (list, tuple)) else d
                for d in widget._transition_new_data
            ]

            old_avg = _avg_from_values(old_vals)
            new_avg = _avg_from_values(new_vals)
            old_max = max(old_vals) if old_vals else 1.0
            new_max = max(new_vals) if new_vals else 1.0
            if old_max <= 0:
                old_max = 1.0
            if new_max <= 0:
                new_max = 1.0

            y_old = margin_top + plot_h - (old_avg / old_max * plot_h) if old_avg > 0 else (margin_top + plot_h)
            y_new = margin_top + plot_h - (new_avg / new_max * plot_h) if new_avg > 0 else (margin_top + plot_h)
            y_avg = y_old + ((y_new - y_old) * t)

            if widget._global_transition_mode == "to_empty":
                tt = max(0.0, min(1.0, t))
                alpha_factor = 1.0 - (tt * tt * (3.0 - (2.0 * tt)))
            elif widget._global_transition_mode == "from_empty":
                tt = max(0.0, min(1.0, t))
                alpha_factor = tt * tt * (3.0 - (2.0 * tt))
            else:
                alpha_factor = 1.0
        else:
            avg_val = widget._get_averages() if zv is None else float(zv.get("avg") or 0.0)
            if avg_val <= 0:
                y_avg = None
            else:
                y_avg = margin_top + plot_h - (avg_val / max_val * plot_h)
            alpha_factor = 1.0

        avg_y = y_avg
        if y_avg is not None:
            _pal = get_theme_colors(widget)
            _base = _pal.get("total_line") or ("#ffffff" if bool(_pal.get("is_dark")) else "#000000")
            avg_pen_target = (_base, bool(widget.hover_avg), alpha_factor, y_avg)

    axis_labels = [l.split(" - ")[0] for l in labels]

    _right_ends = None
    if getattr(widget, "cumulative_visible", False) and cumulative_values:
        right_axis_max = max_cumulative
        if widget._global_transition_mode is not None or widget._data_transition_active:
            old_vals_for_axis = [
                d[1] if isinstance(d, (list, tuple)) else d
                for d in (widget._transition_old_data or [])
            ]
            new_vals_for_axis = [
                d[1] if isinstance(d, (list, tuple)) else d
                for d in (widget._transition_new_data or [])
            ]
            right_axis_max = interpolate_axis_max(
                [sum(old_vals_for_axis)] if old_vals_for_axis else [],
                [sum(new_vals_for_axis)] if new_vals_for_axis else [],
                t,
            )
            _right_ends = (
                interpolate_axis_max([sum(old_vals_for_axis)] if old_vals_for_axis else [], [sum(new_vals_for_axis)] if new_vals_for_axis else [], 0.0),
                interpolate_axis_max([sum(old_vals_for_axis)] if old_vals_for_axis else [], [sum(new_vals_for_axis)] if new_vals_for_axis else [], 1.0),
            )

    use_cached_chrome = (
        (widget._global_transition_mode is None)
        and (not widget._data_transition_active)
        and zv is None
    )
    if zv is not None:
        # Zoom animation: no x labels or stats (the animation fades them), no hover.
        if avg_pen_target is not None:
            _avg_base, _avg_hover, _avg_alpha, avg_y_val = avg_pen_target
            stroke_average_line(
                painter, margin_left, w - margin_right, int(avg_y_val), _avg_base,
                widget=widget, hovered=False, alpha_factor=_avg_alpha,
            )
        if getattr(widget, "cumulative_visible", False) and cumulative_values:
            draw_right_axis_labels(
                painter,
                w,
                h,
                margin_right,
                margin_top,
                margin_bottom,
                right_axis_max,
                value_formatter=widget._axis_value_formatter if widget._is_time_mode() else None,
                widget=widget,
            )
        return
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
            labels=axis_labels,
            stats=widget.get_stats_text() if getattr(widget, "show_stats", False) else [],
            avg_y=avg_y,
            right_axis_max=right_axis_max,
        )
    else:
        if axis_labels and any(axis_labels):
            draw_x_axis_labels(
                painter,
                axis_labels,
                w,
                h,
                margin_left,
                margin_right,
                margin_bottom,
                old_labels=axis_old_labels,
                progress=t,
                widget=widget,
            )
        widget.draw_bottom_stats(painter, plot_w, h, margin_left, margin_bottom)
        if avg_pen_target is not None:
            _avg_base, _avg_hover, _avg_alpha, avg_y_val = avg_pen_target
            stroke_average_line(
                painter, margin_left, w - margin_right, int(avg_y_val), _avg_base,
                widget=widget, hovered=_avg_hover, alpha_factor=_avg_alpha,
            )

    if widget.hover_index != -1 and 0 <= widget.hover_index < n:
        val = values[widget.hover_index]

        if widget.chart_type == "line":
            if n > 1:
                x = margin_left + (widget.hover_index * x_step)
            else:
                x = margin_left
        else:
            if widget._data_transition_active and widget._transition_align_right:
                slots = widget.interpolate_bar_slots(
                    len(widget._transition_old_data),
                    len(widget._transition_new_data),
                    t,
                    margin_left,
                    plot_w,
                    align_right=True,
                )
                if widget.hover_index < len(slots):
                    x = slots[widget.hover_index][0]
                else:
                    width_per_item = plot_w / n
                    x = margin_left + (widget.hover_index * width_per_item) + (width_per_item * 0.5)
            else:
                width_per_item = plot_w / n
                x = margin_left + (widget.hover_index * width_per_item) + (width_per_item * 0.5)

        y = margin_top + plot_h - (val / max_val * plot_h * draw_presence)

        painter.setPen(get_hover_guide_pen(widget, width=1))
        painter.drawLine(QPointF(x, margin_top), QPointF(x, margin_top + plot_h))

        if getattr(widget, "show_hover_marker", True):
            painter.setBrush(widget.color)
            outline_col = get_hover_marker_outline_color(widget)
            outline_col.setAlpha(230 if is_dark else 210)
            painter.setPen(QPen(outline_col, 1.5))
            painter.drawEllipse(QPointF(x, y), 4, 4)

    if getattr(widget, "cumulative_visible", False) and cumulative_values and (not use_cached_chrome):
        if _blend is not None and _right_ends is not None:
            draw_blended_right_labels(
                widget,
                painter,
                _blend,
                width=w,
                height=h,
                margin_right=margin_right,
                margin_top=margin_top,
                margin_bottom=margin_bottom,
                old_max=_right_ends[0],
                new_max=_right_ends[1],
            )
        else:
            draw_right_axis_labels(
                painter,
                w,
                h,
                margin_right,
                margin_top,
                margin_bottom,
                right_axis_max,
                value_formatter=widget._axis_value_formatter if widget._is_time_mode() else None,
                widget=widget,
            )

    widget.draw_selection_overlay(painter, margin_left, margin_top, plot_w, plot_h)



