# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPointF, QRectF, Qt
from ..common.smooth_line import add_smooth_line

from ...chart_utils import ChartGeometry, get_theme_colors, is_night_mode
from ...chart_utils.drawing import (
    stroke_average_line,
    draw_bar_rect,
    bar_fade_factor,
    chart_style,
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


def paint_event_impl(widget, event):
    display_data = widget._get_display_data()
    t = widget.get_progress()
    if widget._data_transition_active and t >= 0.999:
        # Same as the Activity chart: end the transition on its last frame and draw the real data.
        widget._finalize_data_transition()
        widget._invalidate_data_caches()
        display_data = widget._get_display_data()
        t = 1.0
    # Same rule as the Activity chart: growing from / shrinking to an empty chart wins over
    # the relative-height morph, so the bars rise or fall instead of popping.
    use_relative_transition = (
        widget._relative_height_transition
        and widget._data_transition_active
        and widget._global_transition_mode is None
    )
    if use_relative_transition:
        display_data = widget._interpolate_relative_height_rows(t)
    elif widget._global_transition_mode == "from_empty":
        display_data = widget._transition_new_display_data
    elif widget._global_transition_mode == "to_empty":
        display_data = widget._transition_old_display_data
    elif widget._data_transition_active:
        keys = [cfg["key"] for cfg in widget.series_config]
        display_data = widget.interpolate_stacked_rows(
            widget._transition_old_display_data,
            widget._transition_new_display_data,
            keys,
            t,
            align_right=widget._transition_align_right,
        )
    painter = QPainter(widget)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    w = widget.width()
    h = widget.height()

    if widget._data_transition_active:
        totals = []
        for item in display_data:
            totals.append(sum(item.get(cfg["key"], 0) for cfg in widget.series_config))
        cumulative_totals = []
        run_sum = 0.0
        for tval in totals:
            run_sum += tval
            cumulative_totals.append(run_sum)
    else:
        totals = widget._get_totals()
        cumulative_totals = widget._get_cumulative()

    max_val = max(totals) if totals else 1
    if max_val == 0:
        max_val = 1
    max_cumulative = cumulative_totals[-1] if cumulative_totals else 1
    if max_cumulative == 0:
        max_cumulative = 1
    zv = get_zoom_view(widget)
    if zv is not None:
        max_val = max(1e-9, float(zv["max"]))

    bar_display_data = display_data
    bar_scale_max = max_val
    if use_relative_transition:
        bar_scale_max = 1.0

    margin_top = ChartGeometry.MARGIN_TOP
    fm = widget.fontMetrics()

    if widget._global_transition_mode is not None or widget._data_transition_active:
        old_totals_for_margin = [
            sum(item.get(cfg["key"], 0) for cfg in widget.series_config) for item in widget._transition_old_display_data
        ]
        new_totals_for_margin = [
            sum(item.get(cfg["key"], 0) for cfg in widget.series_config) for item in widget._transition_new_display_data
        ]
        old_fmt, new_fmt = transition_margin_formatters(widget)
        margin_left, margin_right = interpolate_margin_pair(
            fm,
            old_totals_for_margin,
            new_totals_for_margin,
            t,
            getattr(widget, "cumulative_visible", False),
            old_formatter=old_fmt,
            new_formatter=new_fmt,
        )
    elif zv is not None:
        margin_left, margin_right = zoom_view_margins(
            zv,
            fm,
            cumulative_totals,
            getattr(widget, "cumulative_visible", False),
            value_formatter=widget._axis_value_formatter if widget._is_time_mode() else None,
        )
    else:
        margin_left, margin_right = calculate_margin_pair(
            fm,
            totals,
            getattr(widget, "cumulative_visible", False),
            value_formatter=widget._axis_value_formatter if widget._is_time_mode() else None,
        )
    avail_w = w - margin_left - margin_right

    margin_bottom = calculate_stats_margin(widget, painter, avail_w)

    avail_h = h - margin_top - margin_bottom
    t_colors = get_theme_colors(widget)
    presence = compute_transition_presence(widget, t, relative_transition=use_relative_transition)

    left_axis_max = max_val
    axis_old_labels = None
    _blend = None
    _left_ends = None
    labels = [item.get("pretty_date", "").split(" - ")[0] for item in display_data]
    if widget._global_transition_mode is not None or widget._data_transition_active:
        old_totals_for_axis = [
            sum(item.get(cfg["key"], 0) for cfg in widget.series_config) for item in (widget._transition_old_display_data or [])
        ]
        new_totals_for_axis = [
            sum(item.get(cfg["key"], 0) for cfg in widget.series_config) for item in (widget._transition_new_display_data or [])
        ]
        left_axis_max = interpolate_axis_max(old_totals_for_axis, new_totals_for_axis, t)
        if widget._global_transition_mode is None:
            _blend = mode_switch_blend(widget, t)
            if _blend is not None:
                _left_ends = (
                    interpolate_axis_max(old_totals_for_axis, new_totals_for_axis, 0.0),
                    interpolate_axis_max(old_totals_for_axis, new_totals_for_axis, 1.0),
                )
        old_label_rows = list(widget._transition_old_display_data or [])
        new_label_rows = list(widget._transition_new_display_data or [])
        if old_label_rows or new_label_rows:
            axis_old_labels, labels = split_transition_labels(
                old_label_rows,
                new_label_rows,
                label_getter=lambda item: item.get("pretty_date", ""),
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

    n = len(bar_display_data)
    if n == 0:
        return

    width_ratio = max(0.05, min(1.0, float(getattr(widget, "_bar_width_ratio", 1.0))))
    width_ratio = min(width_ratio, 0.9)
    if zv is not None:
        widget._zoom_view_plot = (margin_left, margin_top, avail_w, avail_h)
        slot_x0, slot_w = bar_slot(zv, margin_left, avail_w)
        painter.save()
        painter.setClipRect(QRectF(margin_left, 0.0, avail_w, margin_top + avail_h))
    else:
        slot_x0, slot_w = margin_left, avail_w / n
    width_ratio = dense_bar_ratio(slot_w, width_ratio)
    bar_w = slot_w * width_ratio
    bar_slots = None
    if widget._data_transition_active and widget._transition_align_right:
        bar_slots = widget.interpolate_bar_slots(
            len(widget._transition_old_display_data),
            len(widget._transition_new_display_data),
            t,
            margin_left,
            avail_w,
            align_right=True,
            width_ratio=width_ratio,
        )

    _shade_max = float((zv.get("color_max") if zv is not None else None) or bar_scale_max)
    _night = is_night_mode(widget)
    _style_k = chart_style(widget)[1] / 100.0
    _chart_alpha = int(getattr(widget, "chart_opacity_pct", 100) * 2.55)
    _intensity = getattr(widget, "_intensity_by_value_coloring", False)
    _series_colors = {c["key"]: QColor(c["color"]) for c in widget.series_config}
    for i, item in enumerate(bar_display_data):
        if bar_slots and i < len(bar_slots):
            center_x, slot_w = bar_slots[i]
            x = center_x - (slot_w * 0.5)
            draw_bar_w = slot_w
        else:
            x = slot_x0 + (i * slot_w) + (slot_w - bar_w) / 2.0
            draw_bar_w = bar_w
            if zv is not None:
                x, draw_bar_w = zoom_view_bar(zv, i, x, draw_bar_w, slot_x0, slot_w)
        if zv is not None and (x > margin_left + avail_w or x + draw_bar_w < margin_left):
            continue
        current_y = margin_top + avail_h
        _base_y = current_y
        _total_h = sum(
            max(0.0, item.get(_c["key"], 0)) for _c in widget.series_config
        ) / max(1e-9, bar_scale_max) * avail_h * presence
        _size_k = bar_fade_factor(draw_bar_w, _total_h)
        top_key = None
        for _c in widget.series_config:
            if item.get(_c["key"], 0) > 0:
                top_key = _c["key"]

        for config in widget.series_config:
            key = config["key"]
            val = item.get(key, 0)
            if val <= 0:
                continue
            bar_h = (val / bar_scale_max) * avail_h * presence
            y = current_y - bar_h
            rect = QRectF(x, y, draw_bar_w, bar_h)
            alpha = _chart_alpha
            base_color = QColor(_series_colors[key])
            base_color.setAlpha(alpha)

            if _intensity:
                bar_total = sum(item.get(c["key"], 0) for c in widget.series_config)
                ratio = min(1.0, (bar_total / max(1.0, _shade_max))) if _shade_max > 0 else 0.0
                dark = _night
                light_mul = 1.4 if dark else 1.22
                dark_mul = 0.7 if dark else 0.68
                light_l = min(255, int(base_color.lightness() * light_mul))
                dark_l = max(0, int(base_color.lightness() * dark_mul))
                current_l = int(light_l - ((light_l - dark_l) * ratio))
                base_color.setHsl(base_color.hslHue(), base_color.hslSaturation(), current_l)
                base_color.setAlpha(alpha)

            if i == widget.hover_index:
                base_color = base_color.lighter(130) if _night else base_color.darker(115)

            if _size_k > 0.01:
                # Same soft vertical fade as the plain Activity bars, spread over the whole stack.
                _bot = QColor(base_color)
                _top = QColor(base_color)
                _k = _style_k * _size_k
                if _night:
                    _top = _top.lighter(100 + int(round(14 * _k)))
                    _top.setAlpha(base_color.alpha())
                    _bot = _bot.darker(100 + int(round(30 * _k)))
                    _bot.setAlpha(max(30, int(base_color.alpha() * (1.0 - 0.12 * _k))))
                else:
                    _bot.setAlpha(max(30, int(base_color.alpha() * (1.0 - 0.38 * _k))))
                _g = QLinearGradient(0, _base_y - _total_h, 0, _base_y)
                _g.setColorAt(0.0, _top)
                _g.setColorAt(1.0, _bot)
                painter.setBrush(_g)
            else:
                if draw_bar_w < 2.0:
                    # Hair-thin bar: a plain filled rectangle (same picture, much cheaper).
                    painter.fillRect(rect, base_color)
                    current_y = y
                    continue
                painter.setBrush(base_color)
            painter.setPen(Qt.PenStyle.NoPen)
            if key == top_key:
                draw_bar_rect(
                    painter, rect, fade=False,
                    radius=(zv.get("radius", 1.8) if zv is not None else 1.8), widget=widget,
                )
            else:
                painter.drawRect(rect)
            current_y = y

    if getattr(widget, "cumulative_visible", False):
        cumulative_draw_values = cumulative_totals
        cumulative_draw_max = max_cumulative
        if use_relative_transition:
            cumulative_draw_values = widget._interpolate_relative_cumulative(t)
            cumulative_draw_max = 1.0

        # Same as Activity: the total line stays put during the intro reveal and only
        # fades with real empty <-> data transitions.
        line_presence = presence if widget._global_transition_mode in ("from_empty", "to_empty") else 1.0
        path = QPainterPath()
        points = []
        if zv is not None and cumulative_draw_values:
            zv_points, max_cumulative = cumulative_points(zv, cumulative_draw_values, margin_left, avail_w)
            cumulative_draw_values = [v for _x, v in zv_points]
            cumulative_draw_max = max_cumulative
        step_x_line = avail_w / (n - 1) if n > 1 else 0
        x_positions = None
        if widget._data_transition_active and widget._transition_align_right:
            x_positions = widget.interpolate_line_x_positions(
                len(widget._transition_old_display_data),
                len(widget._transition_new_display_data),
                t,
                margin_left,
                avail_w,
                align_right=True,
            )
        for i, cum in enumerate(cumulative_draw_values):
            if zv is not None:
                x = zv_points[i][0]
            elif x_positions and i < len(x_positions):
                x = x_positions[i]
            else:
                x = margin_left + (i * step_x_line) if n > 1 else margin_left + avail_w / 2
            y = margin_top + avail_h - ((cum * line_presence) / cumulative_draw_max * avail_h)
            points.append(QPointF(x, y))

        if points:
            path.moveTo(points[0])
            add_smooth_line(path, points, edge_blend=cumulative_edge_blend(zv, len(points)) if zv is not None else (0.0, 0.0))
            fill_path = QPainterPath(path)
            fill_path.lineTo(points[-1].x(), margin_top + avail_h)
            fill_path.lineTo(points[0].x(), margin_top + avail_h)
            fill_path.closeSubpath()
            painter.save()
            painter.setClipRect(QRectF(margin_left, margin_top - 2.0, avail_w, avail_h + 2.0))
            # Same Total line + soft area as every other chart.
            draw_cumulative_line_and_area(painter, path, fill_path, widget=widget)
            painter.restore()
    if zv is not None:
        painter.restore()

    avg_y = None
    avg_pen_target = None
    right_axis_max = None

    if getattr(widget, "avg_visible", True) and totals:
        def _avg_from_totals(arr):
            if not arr:
                return 0.0
            if getattr(widget, "avg_on_active_days", False):
                non_zeros = [v for v in arr if v > 0]
                return (sum(non_zeros) / len(non_zeros)) if non_zeros else 0.0
            return sum(arr) / len(arr)

        if widget._data_transition_active or widget._global_transition_mode is not None:
            old_totals = [sum(item.get(cfg["key"], 0) for cfg in widget.series_config) for item in widget._transition_old_display_data]
            new_totals = [sum(item.get(cfg["key"], 0) for cfg in widget.series_config) for item in widget._transition_new_display_data]
            old_avg = _avg_from_totals(old_totals)
            new_avg = _avg_from_totals(new_totals)
            old_max = max(old_totals) if old_totals else 1.0
            new_max = max(new_totals) if new_totals else 1.0
            if old_max <= 0:
                old_max = 1.0
            if new_max <= 0:
                new_max = 1.0
            y_old = margin_top + avail_h - (old_avg / old_max * avail_h) if old_avg > 0 else (margin_top + avail_h)
            y_new = margin_top + avail_h - (new_avg / new_max * avail_h) if new_avg > 0 else (margin_top + avail_h)
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
            avg_val = widget._get_avg() if zv is None else float(zv.get("avg") or 0.0)
            if avg_val <= 0:
                y_avg = None
            else:
                y_avg = margin_top + avail_h - (avg_val / max_val * avail_h)
            alpha_factor = 1.0

        avg_y = y_avg
        if y_avg is not None:
            _pal = get_theme_colors(widget)
            _base = _pal.get("total_line") or ("#ffffff" if bool(_pal.get("is_dark")) else "#000000")
            avg_pen_target = (_base, bool(widget.hover_avg), alpha_factor, y_avg)

    _right_ends = None
    if getattr(widget, "cumulative_visible", False) and cumulative_totals:
        right_axis_max = max_cumulative
        if widget._global_transition_mode is not None or widget._data_transition_active:
            old_totals_for_axis = [
                sum(item.get(cfg["key"], 0) for cfg in widget.series_config) for item in (widget._transition_old_display_data or [])
            ]
            new_totals_for_axis = [
                sum(item.get(cfg["key"], 0) for cfg in widget.series_config) for item in (widget._transition_new_display_data or [])
            ]
            right_axis_max = interpolate_axis_max(
                [sum(old_totals_for_axis)] if old_totals_for_axis else [],
                [sum(new_totals_for_axis)] if new_totals_for_axis else [],
                t,
            )
            _right_ends = (
                interpolate_axis_max([sum(old_totals_for_axis)] if old_totals_for_axis else [], [sum(new_totals_for_axis)] if new_totals_for_axis else [], 0.0),
                interpolate_axis_max([sum(old_totals_for_axis)] if old_totals_for_axis else [], [sum(new_totals_for_axis)] if new_totals_for_axis else [], 1.0),
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
        if getattr(widget, "cumulative_visible", False) and cumulative_totals:
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
            plot_w=avail_w,
            labels=labels,
            stats=widget.get_stats_text() if getattr(widget, "show_stats", False) else [],
            avg_y=avg_y,
            right_axis_max=right_axis_max,
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
                progress=t,
                widget=widget,
            )
        widget.draw_bottom_stats(painter, avail_w, h, margin_left, margin_bottom)
        if avg_pen_target is not None:
            _avg_base, _avg_hover, _avg_alpha, avg_y_val = avg_pen_target
            stroke_average_line(
                painter, margin_left, w - margin_right, int(avg_y_val), _avg_base,
                widget=widget, hovered=_avg_hover, alpha_factor=_avg_alpha,
            )

    if widget.hover_index != -1 and 0 <= widget.hover_index < len(display_data):
        if bar_slots and widget.hover_index < len(bar_slots):
            x = bar_slots[widget.hover_index][0]
        else:
            x = margin_left + (widget.hover_index * (avail_w / n)) + (avail_w / n) * 0.5
        painter.setPen(get_hover_guide_pen(widget, width=1))
        painter.drawLine(QPointF(x, margin_top), QPointF(x, margin_top + avail_h))
        if getattr(widget, "show_hover_marker", True):
            item = bar_display_data[widget.hover_index]
            current_y = margin_top + avail_h
            for config in widget.series_config:
                val = item.get(config["key"], 0)
                if val <= 0:
                    continue
                bar_h = (val / bar_scale_max) * avail_h * presence
                y = current_y - bar_h
                painter.setBrush(QColor(config["color"]))
                outline_col = get_hover_marker_outline_color(widget)
                outline_col.setAlpha(230 if bool(t_colors.get("is_dark")) else 210)
                painter.setPen(QPen(outline_col, 1.5))
                painter.drawEllipse(QPointF(x, y + bar_h / 2), 4, 4)
                current_y = y

    if getattr(widget, "cumulative_visible", False) and cumulative_totals and (not use_cached_chrome):
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

    widget.draw_selection_overlay(painter, margin_left, margin_top, avail_w, avail_h)
    if widget._data_transition_active and widget.get_progress() >= 0.999:
        widget._finalize_data_transition()
