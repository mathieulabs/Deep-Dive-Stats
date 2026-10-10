# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QColor, QFont, QFontMetrics, QPainter, QPen, QRectF, Qt

from ....animations.easing import bezier01, smooth01
from ...chart_utils import get_theme_colors
from ...chart_utils.formatting import fmt_num
from .hover_ops import GROW, DIM, PIE_SIZE, SLICE_GAP, hover_amount, hover_display_key, hover_max
from ....logic.logger import log_swallowed
from .layout_ops import refresh_legend_state_impl


def _get_cached_slice_base_colors(widget):
    cache_key = tuple((str(k), int(QColor(v).rgba())) for k, v in sorted((widget.colors or {}).items()))
    cache = getattr(widget, "_slice_base_color_cache", None)
    if cache is None or getattr(widget, "_slice_base_color_cache_key", None) != cache_key:
        built = {str(k): QColor(v) for k, v in (widget.colors or {}).items()}
        widget._slice_base_color_cache_key = cache_key
        widget._slice_base_color_cache = built
        cache = built
    return cache or {}


def _draw_legend(
    widget,
    painter,
    *,
    legend_x_start,
    legend_y_start,
    label_x,
    label_col_right,
    count_col_left,
    count_col_right,
    row_height,
    legend_keys,
    legend_counts,
    total_value,
    text_col,
):
    base_colors = _get_cached_slice_base_colors(widget)
    count_font = QFont(painter.font())
    count_font.setBold(False)
    legend_y = legend_y_start
    for key in legend_keys:
        box_size = 7 if row_height <= 16 else 8
        box_y = legend_y + ((row_height - box_size) / 2.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(base_colors.get(key, QColor("#888888"))))
        painter.drawRect(QRectF(legend_x_start, box_y, box_size, box_size))

        font_bold = QFont(painter.font())
        font_bold.setBold(True)
        painter.setFont(font_bold)
        painter.setPen(QColor(text_col))
        painter.drawText(
            QRectF(label_x, legend_y, max(1, label_col_right - label_x), row_height),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            widget.labels[key],
        )
        painter.setFont(count_font)
        painter.drawText(
            QRectF(count_col_left, legend_y, max(1, count_col_right - count_col_left), row_height),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            fmt_num(int(round(legend_counts.get(key, 0.0)))),
        )
        legend_y += row_height

    legend_y += 4
    font_bold = QFont(painter.font())
    font_bold.setBold(True)
    painter.setFont(font_bold)
    painter.setPen(QColor(text_col))
    painter.drawText(
        QRectF(label_x, legend_y, max(1, label_col_right - label_x), row_height),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        "Total",
    )
    painter.setFont(count_font)
    painter.drawText(
        QRectF(count_col_left, legend_y, max(1, count_col_right - count_col_left), row_height),
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        fmt_num(int(round(total_value))),
    )


def _draw_legend_overlay(widget, painter, keys, counts, total, text_col):
    """Legend shown on hover when it does not fit next to the donut: a small list icon in the
    corner that opens the list of card types over the chart."""
    w, h = widget.width(), widget.height()
    colors = get_theme_colors(widget)
    icon = QRectF(w - 24, 4, 20, 18)
    widget._legend_icon_rect = icon
    hot = bool(getattr(widget, "_legend_hot", False))
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    bg = QColor(colors.get("bg", QColor("#222222")))
    if not hot:
        bg.setAlpha(170)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(icon, 4, 4)
        pen = QPen(QColor(colors.get("text_secondary", QColor("#a1a1aa"))), 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        for i in range(3):
            y = int(icon.top() + 5 + i * 4)
            painter.drawLine(int(icon.left() + 5), y, int(icon.right() - 5), y)
        painter.restore()
        return

    shown = list(keys)
    px, row_h, pad = 11, 16, 8
    room = h - 8 - (2 * pad)
    if (len(shown) + 1) * row_h + 4 > room:
        shown = [k for k in keys if widget.counts.get(k, 0) > 0] or list(keys)
        row_h = max(11, min(row_h, int((room - 4) / (len(shown) + 1))))
        px = max(8, min(px, row_h - 3))
    font = QFont(painter.font())
    font.setPixelSize(px)
    painter.setFont(font)
    fm = QFontMetrics(font)
    max_label_w = max([fm.horizontalAdvance(widget.labels[k]) for k in shown] + [fm.horizontalAdvance("Total")])
    max_count_w = max(
        [fm.horizontalAdvance(fmt_num(int(round(counts.get(k, 0.0))))) for k in shown]
        + [fm.horizontalAdvance(fmt_num(int(round(total))))]
    )
    box = 7 if row_h <= 16 else 8
    pw = min(pad + box + 6 + max_label_w + 12 + max_count_w + pad, w - 8)
    ph = min((2 * pad) + (len(shown) + 1) * row_h + 4, h - 8)
    panel = QRectF(w - 4 - pw, 4, pw, ph)
    widget._legend_panel_rect = panel
    bg.setAlpha(242)
    border = QColor(colors.get("border", QColor("#555555")))
    painter.setPen(QPen(border, 1))
    painter.setBrush(bg)
    painter.drawRoundedRect(panel, 6, 6)
    legend_x_start = panel.left() + pad
    label_x = legend_x_start + box + 6
    count_col_right = panel.right() - pad
    count_col_left = max(label_x + max_label_w + 8, count_col_right - max_count_w - 2)
    label_col_right = max(label_x, count_col_left - 6)
    _draw_legend(
        widget,
        painter,
        legend_x_start=legend_x_start,
        legend_y_start=panel.top() + pad,
        label_x=label_x,
        label_col_right=label_col_right,
        count_col_left=count_col_left,
        count_col_right=count_col_right,
        row_height=row_h,
        legend_keys=shown,
        legend_counts=counts,
        total_value=total,
        text_col=text_col,
    )
    painter.restore()


def paint_event_impl(widget, event):
    painter = QPainter(widget)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    try:
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    except Exception:
        log_swallowed()

    logical_w = 210.0
    w = widget.width()
    h = widget.height()
    refresh_legend_state_impl(widget)
    inline = widget.legend_inline()
    widget._legend_icon_rect = None
    widget._legend_panel_rect = None
    needed_v_h = widget.get_needed_vertical_height()
    is_horizontal = widget.grid_mode and h < needed_v_h - 15 and inline
    painter.save()
    if not inline:
        # Donut only: centred in the box, as large as fits.
        scale = max(0.1, min(w / (PIE_SIZE + 4 * GROW + 8), h / (PIE_SIZE + 4 * GROW + 8), 3.0))
        tx = (w - PIE_SIZE * scale) / 2 - (((logical_w - PIE_SIZE) / 2) * scale)
        ty = (h - PIE_SIZE * scale) / 2 - (5.0 * scale)
        painter.translate(tx, ty)
        painter.scale(scale, scale)
    elif is_horizontal:
        content_w = 252
        h_scale = min(h / 160.0, w / content_w, 3.0)
        total_scaled_w = content_w * h_scale
        tx = (w - total_scaled_w) / 2
        ty = (h - 150 * h_scale) / 2
        painter.translate(tx, ty)
        painter.scale(h_scale, h_scale)
    else:
        scale = widget._get_vertical_scale(logical_w)
        content_h = needed_v_h
        tx = max(2, (w - logical_w * scale) / 2)
        ty = max(2, (h - content_h) / 2)
        painter.translate(tx, ty)
        painter.scale(scale, scale)

    widget._pie_xform = (tx, ty, h_scale if is_horizontal else scale, is_horizontal)
    active_keys = widget._active_keys()
    t = widget.get_progress()
    mode = widget._global_transition_mode
    smooth_t = smooth01(t)
    morph_t = (
        bezier01(smooth_t, 0.18, 0.82)
        if bool(getattr(widget, "_is_data_morph", False))
        else smooth_t
    )
    target_total_for_legend = sum(widget.counts.get(k, 0) for k in active_keys)
    global_alpha = 1.0
    if mode == "from_empty":
        global_alpha = smooth_t
    elif mode == "to_empty":
        global_alpha = 1.0 - smooth_t

    interp_counts = {}
    interp_fractions = None
    total_for_chart = 0.0
    base_colors = _get_cached_slice_base_colors(widget)
    if mode == "to_empty":
        for key in active_keys:
            val = max(0.0, float(widget._prev_counts.get(key, 0)))
            interp_counts[key] = val
            total_for_chart += val
    elif mode == "from_empty":
        for key in active_keys:
            val = max(0.0, float(widget._next_counts.get(key, 0)))
            interp_counts[key] = val
            total_for_chart += val
    else:
        old_total = sum(max(0.0, float(widget._prev_counts.get(k, 0))) for k in active_keys)
        new_total = sum(max(0.0, float(widget._next_counts.get(k, 0))) for k in active_keys)
        if old_total > 0.0 and new_total > 0.0:
            interp_fractions = {}
            for key in active_keys:
                ov = max(0.0, float(widget._prev_counts.get(key, 0)))
                nv = max(0.0, float(widget._next_counts.get(key, 0)))
                old_frac = ov / old_total
                new_frac = nv / new_total
                interp_fractions[key] = max(0.0, old_frac + ((new_frac - old_frac) * morph_t))
            total_for_chart = sum(interp_fractions.values())
        else:
            for key in active_keys:
                ov = float(widget._prev_counts.get(key, 0))
                nv = float(widget._next_counts.get(key, 0))
                val = max(0.0, ov + ((nv - ov) * morph_t))
                interp_counts[key] = val
                total_for_chart += val

    legend_interp_counts = {}
    for key in active_keys:
        ov = max(0.0, float(widget._prev_counts.get(key, 0)))
        nv = max(0.0, float(widget._next_counts.get(key, 0)))
        if mode == "to_empty":
            vv = ov * (1.0 - smooth_t)
        elif mode == "from_empty":
            vv = nv * smooth_t
        else:
            vv = ov + ((nv - ov) * morph_t)
        legend_interp_counts[key] = max(0.0, vv)
    legend_total = sum(legend_interp_counts.values())

    pie_size = 130
    if is_horizontal:
        pie_x = 0
        pie_y = (150 - pie_size) / 2
    else:
        pie_x = (logical_w - pie_size) / 2
        pie_y = 5

    hover_peak = hover_max(widget)
    if total_for_chart > 0:
        start_angle = 90 * 16
        for key in widget.order:
            if key not in active_keys:
                continue
            if interp_fractions is not None:
                fraction = interp_fractions.get(key, 0.0) / max(total_for_chart, 1e-9)
            else:
                val = interp_counts.get(key, 0.0)
                if val <= 0.0001:
                    continue
                fraction = val / total_for_chart
            if fraction <= 0.000001:
                continue

            full_span = -fraction * 360 * 16
            if mode == "to_empty":
                drawn_span = full_span * (1.0 - smooth_t)
            elif mode == "from_empty":
                drawn_span = full_span * smooth_t
            else:
                drawn_span = full_span if widget._is_data_morph else (full_span * t)

            slice_color = QColor(base_colors.get(key, QColor(widget.colors[key])))
            hover_k = hover_amount(widget, key)
            hover_fade = 1.0 - (DIM * hover_peak * (1.0 - hover_k))
            slice_color.setAlpha(int(255 * max(0.0, min(1.0, global_alpha)) * hover_fade * getattr(widget, "chart_opacity_pct", 100) / 100))
            # Donut: each slice is a thick arc (no hole punching). Every slice gives up half a
            # gap at each end, so neighbours never touch or overlap; a very thin slice
            # keeps most of its width.
            ring_w = 22.0
            gap = min(SLICE_GAP, abs(drawn_span) * 0.3)
            span = drawn_span + gap if drawn_span < 0 else drawn_span - gap
            if abs(span) > 1:
                ring_pen = QPen(slice_color, ring_w + (2.0 * GROW * hover_k))
                ring_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
                painter.setPen(ring_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                half = ring_w / 2.0
                painter.drawArc(
                    QRectF(pie_x + half, pie_y + half, pie_size - ring_w, pie_size - ring_w),
                    int(start_angle - gap / 2 if drawn_span < 0 else start_angle + gap / 2),
                    int(span),
                )
            start_angle += drawn_span
    else:
        painter.setPen(QPen(QColor("#555"), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QRectF(pie_x, pie_y, pie_size, pie_size))

    # Total in the middle of the ring (the hovered slice's own numbers while one is hovered).
    hover_key = hover_display_key(widget)
    hover_sub = ""
    if hover_key:
        pct = (legend_interp_counts.get(hover_key, 0.0) / legend_total * 100.0) if legend_total > 0 else 0.0
        hover_sub = f"{widget.labels[hover_key]} {pct:.0f}%"
    try:
        centre_font = QFont(painter.font())
        centre_font.setPixelSize(20)
        centre_font.setBold(True)
        painter.setFont(centre_font)
        painter.setPen(QColor(get_theme_colors(widget).get("text", QColor("#f4f4f5"))))
        painter.drawText(
            QRectF(pie_x, pie_y + (pie_size / 2.0) - 15, pie_size, 22),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            fmt_num(int(round(legend_interp_counts.get(hover_key, 0.0) if hover_key else legend_total))),
        )
        sub_font = QFont(centre_font)
        sub_font.setPixelSize(10 if hover_key else 11)
        sub_font.setBold(False)
        painter.setFont(sub_font)
        sub_col = QColor(get_theme_colors(widget).get("text_secondary", QColor("#a1a1aa")))
        painter.setPen(sub_col)
        painter.drawText(
            QRectF(pie_x, pie_y + (pie_size / 2.0) + 6, pie_size, 14),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            hover_sub if hover_key else "cards",
        )
    except Exception:
        log_swallowed()
    painter.restore()

    if not inline:
        if widget.show_legend:
            _draw_legend_overlay(
                widget,
                painter,
                [k for k in widget.order if k in active_keys],
                legend_interp_counts,
                legend_total,
                QColor(get_theme_colors(widget).get("text", QColor("#f4f4f5"))),
            )
        if t >= 0.999:
            widget._is_data_morph = False
            if mode != "to_empty":
                widget._global_transition_mode = None
                widget._prev_counts = dict(widget._next_counts)
        return

    if is_horizontal:
        legend_scale = h_scale
        pie_rect = QRectF(
            tx + (pie_x * h_scale),
            ty + (pie_y * h_scale),
            pie_size * h_scale,
            pie_size * h_scale,
        )
        legend_x_start = pie_rect.right() + max(6.0, 8.0 * legend_scale)
        legend_y = ty + max(8.0, 10.0 * legend_scale)
        legend_right = tx + total_scaled_w - max(4.0, 4.0 * legend_scale)
    else:
        legend_scale = scale
        legend_x_start = tx + (5.0 * scale)
        legend_y = ty + ((pie_y + pie_size + 15.0) * scale)
        legend_right = tx + (logical_w * scale) - max(5.0, 5.0 * scale)

    font = painter.font()
    width_scale = max(0.75, min(1.5, max(1.0, legend_right - legend_x_start) / 130.0))
    font_px = max(9, min(18, int(round(12 * min(legend_scale, width_scale)))))
    font.setPixelSize(font_px)
    painter.setFont(font)
    fm = QFontMetrics(font)
    row_height = max(font_px + 4, int(round((16 if is_horizontal else 18) * legend_scale)))
    t_colors = get_theme_colors(widget)
    text_col = t_colors.get("text", QColor("#f4f4f5"))

    legend_keys = [k for k in widget.order if k in active_keys]
    if is_horizontal:
        # Short card (zoomed-out interface): squeeze the legend into the height there is.
        room = h - legend_y - 4
        if (len(legend_keys) + 1) * row_height + 4 > room:
            nonzero = [k for k in legend_keys if widget.counts.get(k, 0) > 0]
            if nonzero:
                legend_keys = nonzero
            row_height = max(10, min(row_height, int((room - 4) / (len(legend_keys) + 1))))
            font_px = max(7, min(font_px, row_height - 3))
            font.setPixelSize(font_px)
            painter.setFont(font)
            fm = QFontMetrics(font)
    max_label_w = max([fm.horizontalAdvance(widget.labels[k]) for k in legend_keys] + [fm.horizontalAdvance("Total")]) if legend_keys else fm.horizontalAdvance("Total")
    max_count_w = max([fm.horizontalAdvance(fmt_num(widget.counts.get(k, 0))) for k in legend_keys] + [fm.horizontalAdvance(fmt_num(int(target_total_for_legend)))]) if legend_keys else fm.horizontalAdvance("0")

    if is_horizontal:
        # The text keeps a minimum pixel size while the donut keeps shrinking, so on a
        # short card the legend can run past the right edge: shrink the text a bit
        # and pull the legend toward the donut until it fits.
        label_gap = max(9.0, 12.0 * legend_scale)
        x_min = pie_rect.right() + 4
        while x_min + label_gap + max_label_w + 8 + max_count_w + 2 > w - 3 and font_px > 6:
            font_px -= 1
            font.setPixelSize(font_px)
            painter.setFont(font)
            fm = QFontMetrics(font)
            max_label_w = max([fm.horizontalAdvance(widget.labels[k]) for k in legend_keys] + [fm.horizontalAdvance("Total")]) if legend_keys else fm.horizontalAdvance("Total")
            max_count_w = max([fm.horizontalAdvance(fmt_num(widget.counts.get(k, 0))) for k in legend_keys] + [fm.horizontalAdvance(fmt_num(int(target_total_for_legend)))]) if legend_keys else fm.horizontalAdvance("0")
        legend_need = label_gap + max_label_w + 8 + max_count_w + 2
        if legend_x_start + legend_need > w - 3:
            legend_x_start = max(x_min, (w - 3) - legend_need)
        legend_right = min(max(legend_right, legend_x_start + legend_need), w - 3)
    label_x = legend_x_start + max(9.0, 12.0 * legend_scale)
    count_col_right = legend_right
    count_col_left = max(label_x + max_label_w + 10, count_col_right - max_count_w - 2)
    label_col_right = max(label_x, count_col_left - 6)
    _draw_legend(
        widget,
        painter,
        legend_x_start=legend_x_start,
        legend_y_start=legend_y,
        label_x=label_x,
        label_col_right=label_col_right,
        count_col_left=count_col_left,
        count_col_right=count_col_right,
        row_height=row_height,
        legend_keys=legend_keys,
        legend_counts=legend_interp_counts,
        total_value=legend_total,
        text_col=text_col,
    )

    if t >= 0.999:
        widget._is_data_morph = False
        if mode != "to_empty":
            widget._global_transition_mode = None
            widget._prev_counts = dict(widget._next_counts)
