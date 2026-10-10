# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..common.cache_dpr import cache_dpr, cache_surface, draw_cache, stale_cache, raster_dpr
from aqt.qt import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPointF, QRectF, Qt
from ..common.smooth_line import add_smooth_line

from ...chart_utils.drawing import (
    draw_bar_rect,
    draw_grid_and_axes,
    draw_right_axis_labels,
    scale_line_alpha,
)
from ...chart_utils.geometry import ChartGeometry
from ...chart_utils.theme import get_theme_colors, is_night_mode
from ..common.stats import draw_chart_bottom_stats
from ...chart_utils.drawing import chart_axes_style, total_line_params
from ..common.cache_keys import series_cache_token as _series_cache_token, theme_color_token as _theme_color_token



def _fill_soft_vertical(painter, fill_path, brush):
    """Fill `fill_path` with `brush`, fading to nothing towards the baseline (same soft
    look as the Total area of the other charts). Drawn through a small offscreen layer
    so the existing horizontal alpha ramp (hour appear/disappear) keeps working."""
    from aqt.qt import QImage, QRect

    br = fill_path.boundingRect().toAlignedRect().adjusted(-1, -1, 1, 1)
    if br.width() <= 0 or br.height() <= 0:
        painter.fillPath(fill_path, brush)
        return
    dpr = raster_dpr(None, painter)  # export: at the export's resolution
    img = QImage(max(1, int(br.width() * dpr)), max(1, int(br.height() * dpr)), QImage.Format.Format_ARGB32_Premultiplied)
    img.setDevicePixelRatio(dpr)
    img.fill(0)
    ip = QPainter(img)
    ip.setRenderHint(QPainter.RenderHint.Antialiasing)
    ip.translate(-br.left(), -br.top())
    ip.fillPath(fill_path, brush)
    ip.resetTransform()
    ip.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    fade = QLinearGradient(0, 0, 0, br.height())
    # Same falloff as the Total area of the other charts: eased, gone at the baseline.
    fade.setColorAt(0.0, QColor(0, 0, 0, 255))
    fade.setColorAt(0.55, QColor(0, 0, 0, 77))
    fade.setColorAt(1.0, QColor(0, 0, 0, 0))
    ip.fillRect(QRect(0, 0, br.width(), br.height()), fade)
    ip.end()
    painter.drawImage(br.topLeft(), img)

def _draw_cached_scaffold(widget, painter, *, width, height, margin_left, margin_top, margin_right, margin_bottom, max_val):
    theme = get_theme_colors(widget)
    cache_key = (
        int(width),
        int(height),
        int(margin_left),
        int(margin_top),
        int(margin_right),
        int(margin_bottom),
        int(round(float(max_val))),
        _theme_color_token(theme.get("text")),
        _theme_color_token(theme.get("text_secondary")),
        _theme_color_token(theme.get("grid")),
        chart_axes_style(widget),  # Settings > Chart Style: grid / quiet axes
        bool(getattr(widget, "show_cumulative_axis", True)),
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
            )
            draw_x_axis_impl(widget, scaffold_painter, width - margin_left - margin_right, height, margin_left, margin_bottom)
            if bool(getattr(widget, "show_cumulative_axis", True)):
                draw_right_axis_labels(
                    scaffold_painter,
                    width,
                    height,
                    margin_right,
                    margin_top,
                    margin_bottom,
                    100,
                    grid_lines=5,
                    suffix="%",
                    widget=widget,
                )
        finally:
            scaffold_painter.end()
        widget._scaffold_cache_key = cache_key
        widget._scaffold_cache_pixmap = px
        pixmap = px

    if pixmap is not None:
        draw_cache(painter, pixmap)


def _draw_cached_overlay(
    widget,
    painter,
    *,
    width,
    height,
    plot_w,
    plot_h,
    margin_left,
    margin_top,
    margin_bottom,
    rates,
    active_mask,
    visibility,
    disappearing_mask,
    stats,
):
    theme = get_theme_colors(widget)
    cache_key = (
        int(width),
        int(height),
        int(round(float(plot_w))),
        int(round(float(plot_h))),
        int(margin_left),
        int(margin_top),
        int(margin_bottom),
        bool(getattr(widget, "show_cumulative_axis", True)),
        bool(getattr(widget, "show_stats", False)),
        _series_cache_token(rates),
        tuple(bool(v) for v in (active_mask or [])),
        _series_cache_token(visibility),
        tuple(bool(v) for v in (disappearing_mask or [])),
        tuple(str(s) for s in (stats or [])),
        _theme_color_token(theme.get("text")),
        _theme_color_token(theme.get("text_secondary")),
        _theme_color_token(theme.get("total_line")),
        str(widget.font().family()),
    )

    pixmap = getattr(widget, "_overlay_cache_pixmap", None)
    if pixmap is None or stale_cache(pixmap) or getattr(widget, "_overlay_cache_key", None) != cache_key or pixmap.devicePixelRatio() + 0.01 < cache_dpr(widget, painter):
        dpr = 1.0
        try:
            dpr = cache_dpr(widget, painter)
        except Exception:
            dpr = 1.0
        px = cache_surface(max(1, int(round(width * dpr))), max(1, int(round(height * dpr))))
        px.setDevicePixelRatio(dpr)
        px.fill(Qt.GlobalColor.transparent)
        overlay_painter = QPainter(px)
        try:
            overlay_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            if bool(getattr(widget, "show_cumulative_axis", True)):
                widget.draw_success_rate_area(
                    overlay_painter,
                    plot_w,
                    plot_h,
                    margin_left,
                    margin_top,
                    rates,
                    active_mask,
                    visibility,
                    disappearing_mask,
                )
            if bool(getattr(widget, "show_stats", False)):
                draw_chart_bottom_stats(
                    widget,
                    overlay_painter,
                    plot_w,
                    height,
                    margin_left,
                    margin_bottom,
                    stats=stats,
                )
        finally:
            overlay_painter.end()
        widget._overlay_cache_key = cache_key
        widget._overlay_cache_pixmap = px
        pixmap = px

    if pixmap is not None:
        draw_cache(painter, pixmap)


def paint_event_impl(widget, event):
    if not widget.data_dict:
        return

    painter = QPainter(widget)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    w = widget.width()
    h = widget.height()

    t = widget.get_progress()
    if t >= 0.995:
        t = 1.0
    totals, correct = widget._snapshot_from_data(widget.data_dict)
    draw_totals = totals
    draw_rates = []
    draw_active_mask = []
    draw_visibility = []
    draw_disappearing_mask = []
    axis_max = widget.max_val
    draw_ratios = [max(0.0, (v / max(1.0, axis_max))) for v in draw_totals]
    for h_idx in range(24):
        tot = totals[h_idx] if h_idx < len(totals) else 0.0
        cor = correct[h_idx] if h_idx < len(correct) else 0.0
        vis = 1.0 if tot > 0.0 else 0.0
        draw_visibility.append(vis)
        draw_active_mask.append(tot > 0.0)
        draw_disappearing_mask.append(False)
        draw_rates.append((cor / tot) if tot > 0.0 else 0.0)
    if widget._data_transition_active:
        old_totals = widget._transition_old_totals
        new_totals = widget._transition_new_totals
        old_correct = widget._transition_old_correct
        new_correct = widget._transition_new_correct
        draw_totals = widget._interpolate_series_fast(old_totals, new_totals, t)
        old_max = max(old_totals) if old_totals and max(old_totals) > 0 else 1.0
        new_max = max(new_totals) if new_totals and max(new_totals) > 0 else 1.0
        axis_max = max(1.0, old_max + ((new_max - old_max) * t))
        transition_cache = getattr(widget, "_data_transition_render_cache", {}) or {}
        old_draw_ratios = transition_cache.get("old_draw_ratios") or []
        new_draw_ratios = transition_cache.get("new_draw_ratios") or []
        transition_slots = transition_cache.get("transition_slots") or []
        draw_ratios = []
        for ov, nv in zip(old_totals, new_totals):
            idx = len(draw_ratios)
            r0 = old_draw_ratios[idx] if idx < len(old_draw_ratios) else max(0.0, ov / old_max)
            r1 = new_draw_ratios[idx] if idx < len(new_draw_ratios) else max(0.0, nv / new_max)
            draw_ratios.append(max(0.0, min(1.0, r0 + ((r1 - r0) * t))))
        draw_rates = []
        draw_active_mask = []
        draw_visibility = []
        draw_disappearing_mask = []
        # The animation uses an OutCubic curve (fast start), which made the total
        # line pop in. Fade it along (roughly) linear time with a smoothstep instead.
        _lin = 1.0 - (max(0.0, 1.0 - t) ** (1.0 / 3.0))
        _line_t = _lin * _lin * (3.0 - 2.0 * _lin)
        for h_idx in range(24):
            slot = transition_slots[h_idx] if h_idx < len(transition_slots) else None
            ot = old_totals[h_idx] if h_idx < len(old_totals) else 0.0
            nt = new_totals[h_idx] if h_idx < len(new_totals) else 0.0
            old_rate = slot.get("old_rate", 0.0) if slot else ((old_correct[h_idx] / ot) if ot > 0.0 and h_idx < len(old_correct) else 0.0)
            new_rate = slot.get("new_rate", 0.0) if slot else ((new_correct[h_idx] / nt) if nt > 0.0 and h_idx < len(new_correct) else 0.0)
            old_active = bool(slot.get("old_active", False)) if slot else (ot > 0.0)
            new_active = bool(slot.get("new_active", False)) if slot else (nt > 0.0)
            if old_active and new_active:
                rate = old_rate + ((new_rate - old_rate) * t)
                vis = 1.0
                active = True
                is_disappearing = False
            elif old_active and not new_active:
                rate = old_rate
                vis = 1.0 - _line_t
                active = (vis > 0.001) and (t < 0.999)
                is_disappearing = True
            elif (not old_active) and new_active:
                rate = new_rate
                vis = _line_t
                active = True
                is_disappearing = False
            else:
                rate = 0.0
                vis = 0.0
                active = False
                is_disappearing = False
            draw_rates.append(max(0.0, min(1.0, rate)))
            draw_visibility.append(max(0.0, min(1.0, vis)))
            draw_active_mask.append(active)
            draw_disappearing_mask.append(is_disappearing)

    margin_left = ChartGeometry.calculate_dynamic_left_margin(widget.fontMetrics(), axis_max)
    if widget._data_transition_active:
        old_left = ChartGeometry.calculate_dynamic_left_margin(widget.fontMetrics(), max(1.0, widget._transition_old_max))
        new_left = ChartGeometry.calculate_dynamic_left_margin(widget.fontMetrics(), max(1.0, widget._transition_new_max))
        margin_left = int(round(old_left + ((new_left - old_left) * t)))
    margin_right = widget._get_margin_right()
    plot_w = w - margin_left - margin_right

    show_stats = getattr(widget, "show_stats", False)
    if show_stats:
        stats = widget.get_stats_text()
        margin_bottom = ChartGeometry.calculate_stats_margin(stats, plot_w, widget.fontMetrics())
    else:
        margin_bottom = ChartGeometry.MARGIN_BOTTOM
        stats = []

    margin_top = ChartGeometry.MARGIN_TOP
    plot_h = h - margin_bottom - margin_top

    _draw_cached_scaffold(
        widget,
        painter,
        width=w,
        height=h,
        margin_left=margin_left,
        margin_top=margin_top,
        margin_right=margin_right,
        margin_bottom=margin_bottom,
        max_val=axis_max,
    )

    widget.draw_bars(painter, plot_w, plot_h, margin_left, margin_top, draw_totals, draw_ratios)
    if widget._data_transition_active:
        if bool(getattr(widget, "show_cumulative_axis", True)):
            widget.draw_success_rate_area(
                painter, plot_w, plot_h, margin_left, margin_top, draw_rates, draw_active_mask, draw_visibility, draw_disappearing_mask
            )
        widget.draw_bottom_stats(painter, plot_w, h, margin_left, margin_bottom)
    else:
        _draw_cached_overlay(
            widget,
            painter,
            width=w,
            height=h,
            plot_w=plot_w,
            plot_h=plot_h,
            margin_left=margin_left,
            margin_top=margin_top,
            margin_bottom=margin_bottom,
            rates=draw_rates,
            active_mask=draw_active_mask,
            visibility=draw_visibility,
            disappearing_mask=draw_disappearing_mask,
            stats=stats,
        )
    if widget._data_transition_active and widget.get_progress() >= 0.999:
        widget._data_transition_active = False
        widget._transition_old_totals = [0.0] * 24
        widget._transition_new_totals = [0.0] * 24
        widget._transition_old_correct = [0.0] * 24
        widget._transition_new_correct = [0.0] * 24
        widget._transition_old_max = 1.0
        widget._transition_new_max = 1.0
        widget._data_transition_render_cache = {}


def draw_bottom_stats_impl(widget, painter, plot_w, h, margin_left, margin_bottom):
    return draw_chart_bottom_stats(widget, painter, plot_w, h, margin_left, margin_bottom)


def draw_success_rate_area_impl(widget, painter, plot_w, plot_h, margin_left, margin_top, rates, active_mask, visibility, disappearing_mask):
    # One continuous line through the centre of every active hour. Each point has
    # its own visibility and the color ramps between points, so hours entering or
    # leaving fade instead of popping or splitting the line.
    n = 24
    step_x = plot_w / n
    runs = []
    cur = []
    for h_idx in range(n):
        a = bool(active_mask[h_idx]) if h_idx < len(active_mask) else False
        if a:
            cur.append(h_idx)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)

    pal = get_theme_colors(widget)
    is_dark = pal["is_dark"]
    base_fill_alpha = scale_line_alpha(52 if is_dark else 38, widget)  # as the other charts' Total area
    base_line_alpha = scale_line_alpha(100 if is_dark else 95, widget)
    base_qc = QColor(pal.get("text_secondary", pal["total_line"]))
    tr, tg, tb = base_qc.red(), base_qc.green(), base_qc.blue()
    halo_base = QColor(pal.get("bg", QColor("#000000" if is_dark else "#ffffff")))
    # Same total-line look as the other charts: finer line, lighter halo.
    tl = total_line_params(pal, widget)
    line_w, halo_w, halo_a = tl["width"], tl["halo_width"], tl["halo_alpha"]
    base_line_alpha = tl["alpha"]
    halo_base = tl["halo"]
    line_qc = tl["color"]
    lr, lg, lb = line_qc.red(), line_qc.green(), line_qc.blue()
    hr_, hg_, hb_ = halo_base.red(), halo_base.green(), halo_base.blue()
    base_y = margin_top + plot_h

    for run in runs:
        pts = []
        for h_idx in run:
            rv = max(0.0, min(1.0, float(rates[h_idx] if h_idx < len(rates) else 0.0)))
            vis = max(0.0, min(1.0, float(visibility[h_idx] if h_idx < len(visibility) else 1.0)))
            pts.append((margin_left + (h_idx + 0.5) * step_x, margin_top + plot_h - (rv * plot_h), vis))
        if max(p[2] for p in pts) <= 0.002:
            continue

        x0, x1 = pts[0][0], pts[-1][0]
        single_point_run = len(pts) == 1
        if len(pts) == 1:
            half = step_x * 0.32
            pts = [(x0 - half, pts[0][1], pts[0][2]), (x0 + half, pts[0][1], pts[0][2])]
            x0, x1 = pts[0][0], pts[-1][0]
        else:
            # A run that reaches the first / last hour continues flat to the plot edge,
            # so the line spans the whole chart instead of stopping mid-bar.
            if run[0] == 0:
                pts.insert(0, (float(margin_left), pts[0][1], pts[0][2]))
            if run[-1] == n - 1:
                pts.append((float(margin_left + plot_w), pts[-1][1], pts[-1][2]))
            x0, x1 = pts[0][0], pts[-1][0]

        path = QPainterPath()
        path.moveTo(pts[0][0], pts[0][1])
        add_smooth_line(path, [QPointF(px, py) for px, py, _v in pts])

        fill_path = QPainterPath(path)
        fill_path.lineTo(x1, base_y)
        fill_path.lineTo(x0, base_y)
        fill_path.closeSubpath()

        span = max(1e-6, x1 - x0)

        def _ramp(alpha_fn):
            # Each segment takes the visibility of its least visible end, constant along
            # the segment. A segment bridging an appearing hour stays invisible until that
            # hour fades in.
            g = QLinearGradient(x0, 0, x1, 0)
            eps = 1e-4
            for i in range(len(pts) - 1):
                a = min(pts[i][2], pts[i + 1][2])
                p0 = max(0.0, min(1.0, (pts[i][0] - x0) / span))
                p1 = max(0.0, min(1.0, (pts[i + 1][0] - x0) / span))
                g.setColorAt(min(1.0, p0 + (eps if i > 0 else 0.0)), alpha_fn(a))
                g.setColorAt(max(0.0, p1 - (eps if i < len(pts) - 2 else 0.0)), alpha_fn(a))
            return g

        _fill_soft_vertical(
            painter,
            fill_path,
            _ramp(lambda v: QColor(tr, tg, tb, int(round(base_fill_alpha * v)))),
        )

        halo_pen = QPen(QColor(hr_, hg_, hb_, halo_a), halo_w)
        halo_pen.setBrush(_ramp(lambda v: QColor(hr_, hg_, hb_, int(round(halo_a * v)))))
        halo_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        halo_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.strokePath(path, halo_pen)

        pen = QPen(QColor(lr, lg, lb, base_line_alpha), line_w)
        pen.setBrush(_ramp(lambda v: QColor(lr, lg, lb, int(round(base_line_alpha * v)))))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.strokePath(path, pen)

        # An hour whose neighbours are still invisible is drawn as a short stub, like an
        # isolated hour in the static chart, and hands over to the connecting segments
        # as they fade in.
        if len(pts) > 2 or single_point_run is False:
            n_pts = len(pts)
            for i, (px, py, vis) in enumerate(pts):
                seg_l = min(pts[i - 1][2], vis) if i > 0 else 0.0
                seg_r = min(pts[i + 1][2], vis) if i < n_pts - 1 else 0.0
                stub_a = vis - max(seg_l, seg_r)
                if stub_a <= 0.01:
                    continue
                half = step_x * 0.32
                stub = QPainterPath()
                stub.moveTo(px - half, py)
                stub.lineTo(px + half, py)
                spen = QPen(QColor(lr, lg, lb, int(round(base_line_alpha * stub_a))), line_w)
                spen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.strokePath(stub, spen)


def draw_bars_impl(widget, painter, plot_w, plot_h, margin_left, margin_top, totals, draw_ratios):
    n = 24
    step_x = plot_w / n
    bar_w = step_x * 0.9
    if bar_w < 1:
        bar_w = 1
    base_color = QColor(widget.bar_color)

    painter.setPen(Qt.PenStyle.NoPen)
    intro = 1.0 if widget._data_transition_active else max(0.0, min(1.0, float(widget.get_progress())))
    for h_idx in range(24):
        total = totals[h_idx] if h_idx < len(totals) else 0.0
        if total == 0:
            continue
        x = margin_left + (h_idx * step_x) + (step_x - bar_w) / 2
        ratio_for_height = draw_ratios[h_idx] if h_idx < len(draw_ratios) else 0.0
        bar_h = ratio_for_height * plot_h * intro
        y = margin_top + plot_h - bar_h

        ratio = min(1.0, ratio_for_height) if ratio_for_height > 0 else 0
        c = QColor(base_color)
        dark = is_night_mode(widget)
        light_mul = 1.4 if dark else 1.22
        dark_mul = 0.7 if dark else 0.68
        light_l = min(255, int(c.lightness() * light_mul))
        dark_l = max(0, int(c.lightness() * dark_mul))
        current_l = int(light_l - ((light_l - dark_l) * ratio))
        c.setHsl(c.hslHue(), c.hslSaturation(), current_l)
        c.setAlpha(int(getattr(widget, "chart_opacity_pct", 100) * 2.55))

        if h_idx == widget.hover_index:
            c = c.lighter(130) if dark else c.darker(115)
            c.setAlpha(255)

        painter.setBrush(c)
        draw_bar_rect(painter, QRectF(x, y, bar_w, bar_h), widget=widget)


def draw_x_axis_impl(widget, painter, plot_w, total_h, margin_left, margin_bottom):
    painter.setPen(get_theme_colors(widget).get("text_secondary", QColor("#888888")))
    font = painter.font()
    font.setPixelSize(10)
    painter.setFont(font)

    n = 24
    step_x = plot_w / n
    skip = 1
    if step_x < 10:
        skip = 4
    elif step_x < 20:
        skip = 2

    for h_idx in range(24):
        if h_idx % skip != 0:
            continue
        x = margin_left + (h_idx * step_x) + (step_x / 2)
        t_rect = QRectF(x - 10, total_h - margin_bottom + 5, 20, 15)
        painter.drawText(t_rect, Qt.AlignmentFlag.AlignCenter, f"{h_idx}")
