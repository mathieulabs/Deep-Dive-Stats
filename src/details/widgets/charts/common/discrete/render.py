# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..cache_dpr import cache_dpr, cache_surface, draw_cache, stale_cache
from aqt.qt import QColor, QPainter, QPainterPath, QPointF, Qt
from ..smooth_line import add_smooth_line

from ....chart_utils.drawing import draw_grid_and_axes
from ....chart_utils.geometry import ChartGeometry
from ....chart_utils.drawing import chart_axes_style
from ..cache_keys import theme_color_token as _theme_color_token


def draw_cached_discrete_scaffold(
    widget,
    painter,
    *,
    width,
    height,
    margin_left,
    margin_top,
    margin_right,
    margin_bottom,
    axis_max,
    max_cumulative=None,
):
    try:
        from ....chart_utils.theme import get_theme_colors

        theme = get_theme_colors(widget)
    except Exception:
        theme = {}

    cache_key = (
        int(width),
        int(height),
        int(margin_left),
        int(margin_top),
        int(margin_right),
        int(margin_bottom),
        int(round(float(axis_max or 0.0))),
        None if max_cumulative is None else int(round(float(max_cumulative or 0.0))),
        bool(getattr(widget, "show_cumulative_axis", True)),
        _theme_color_token(theme.get("text")),
        _theme_color_token(theme.get("text_secondary")),
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
                axis_max,
                max_cumulative=max_cumulative if bool(getattr(widget, "show_cumulative_axis", True)) else None,
                widget=widget,
            )
        finally:
            scaffold_painter.end()
        widget._scaffold_cache_key = cache_key
        widget._scaffold_cache_pixmap = px
        pixmap = px

    if pixmap is not None:
        draw_cache(painter, pixmap)


def _resolve_transition_count_attrs(count_attr):
    name = str(count_attr or "points_count").strip() or "points_count"
    return f"_transition_old_{name}", f"_transition_new_{name}"


def compute_discrete_draw_state(
    widget,
    *,
    axis_max=None,
    t=None,
    base_count_attr="_points_count",
    transition_count_attr="points_count",
):
    progress = widget.get_progress() if t is None else t
    draw_values = [float(v or 0.0) for v in (widget._display_values or [])]
    resolved_axis_max = axis_max if axis_max is not None else (widget.max_val if widget.max_val > 0 else 1.0)
    draw_ratios = [max(0.0, (v / max(1.0, resolved_axis_max))) for v in draw_values]
    draw_points_count = int(getattr(widget, base_count_attr, 0) or len(draw_values))

    if widget._data_transition_active:
        old_vals = widget._transition_old_values or []
        new_vals = widget._transition_new_values or []
        old_max = max(old_vals) if old_vals and max(old_vals) > 0 else 1.0
        new_max = max(new_vals) if new_vals and max(new_vals) > 0 else 1.0
        resolved_axis_max = max(1.0, old_max + ((new_max - old_max) * progress))
        draw_values = widget.interpolate_numeric_series(old_vals, new_vals, progress, align_right=widget._transition_align_right)
        n = max(len(old_vals), len(new_vals))
        if widget._transition_align_right:
            old_pad = ([0.0] * (n - len(old_vals))) + list(old_vals)
            new_pad = ([0.0] * (n - len(new_vals))) + list(new_vals)
        else:
            old_pad = list(old_vals) + ([0.0] * (n - len(old_vals)))
            new_pad = list(new_vals) + ([0.0] * (n - len(new_vals)))
        draw_ratios = []
        for ov, nv in zip(old_pad, new_pad):
            r0 = max(0.0, ov / old_max)
            r1 = max(0.0, nv / new_max)
            draw_ratios.append(max(0.0, min(1.0, r0 + ((r1 - r0) * progress))))
        old_count_attr, new_count_attr = _resolve_transition_count_attrs(transition_count_attr)
        draw_points_count = max(
            int(getattr(widget, old_count_attr, 0) or 0),
            int(getattr(widget, new_count_attr, 0) or 0),
        )

    return draw_values, draw_ratios, draw_points_count, resolved_axis_max


def compute_discrete_chart_margins(widget, painter, *, axis_max, draw_values, t=None):
    progress = widget.get_progress() if t is None else t
    margin_left = ChartGeometry.calculate_dynamic_left_margin(widget.fontMetrics(), axis_max)
    margin_right = ChartGeometry.calculate_dynamic_right_margin(
        widget.fontMetrics(),
        [sum(draw_values)],
        bool(getattr(widget, "show_cumulative_axis", True)),
    )
    margin_top = ChartGeometry.MARGIN_TOP

    if widget._data_transition_active:
        old_left = ChartGeometry.calculate_dynamic_left_margin(widget.fontMetrics(), max(1.0, widget._transition_old_max))
        new_left = ChartGeometry.calculate_dynamic_left_margin(widget.fontMetrics(), max(1.0, widget._transition_new_max))
        margin_left = int(round(old_left + ((new_left - old_left) * progress)))
        old_total = sum(widget._transition_old_values or [])
        new_total = sum(widget._transition_new_values or [])
        old_right = ChartGeometry.calculate_dynamic_right_margin(
            widget.fontMetrics(),
            [old_total],
            bool(getattr(widget, "show_cumulative_axis", True)),
        )
        new_right = ChartGeometry.calculate_dynamic_right_margin(
            widget.fontMetrics(),
            [new_total],
            bool(getattr(widget, "show_cumulative_axis", True)),
        )
        margin_right = int(round(old_right + ((new_right - old_right) * progress)))

    plot_w = widget.width() - margin_left - margin_right
    if getattr(widget, "show_stats", False):
        stats = widget.get_stats_text()
        margin_bottom = ChartGeometry.calculate_stats_margin(stats, plot_w, painter.fontMetrics())
    else:
        margin_bottom = ChartGeometry.MARGIN_BOTTOM
    plot_h = widget.height() - margin_bottom - margin_top
    return margin_left, margin_right, margin_top, margin_bottom, plot_w, plot_h


def prepare_discrete_paint_state(
    widget,
    painter,
    *,
    axis_max=None,
    t=None,
    base_count_attr="_points_count",
    anim_count_attr="_anim_draw_points_count",
    transition_count_attr="points_count",
):
    progress = widget.get_progress() if t is None else t
    resolved_axis_max = axis_max if axis_max is not None else (widget.max_val if widget.max_val > 0 else 1.0)
    draw_values, draw_ratios, draw_points_count, resolved_axis_max = compute_discrete_draw_state(
        widget,
        axis_max=resolved_axis_max,
        t=progress,
        base_count_attr=base_count_attr,
        transition_count_attr=transition_count_attr,
    )
    widget._anim_draw_values = draw_values
    widget._anim_draw_ratios = draw_ratios
    setattr(widget, anim_count_attr, draw_points_count)

    margin_left, margin_right, margin_top, margin_bottom, plot_w, plot_h = compute_discrete_chart_margins(
        widget,
        painter,
        axis_max=resolved_axis_max,
        draw_values=draw_values,
        t=progress,
    )
    total_cards = sum(draw_values)
    if total_cards == 0:
        total_cards = 1

    return {
        "t": progress,
        "axis_max": resolved_axis_max,
        "draw_values": draw_values,
        "draw_ratios": draw_ratios,
        "draw_points_count": draw_points_count,
        "margin_left": margin_left,
        "margin_right": margin_right,
        "margin_top": margin_top,
        "margin_bottom": margin_bottom,
        "plot_w": plot_w,
        "plot_h": plot_h,
        "total_cards": total_cards,
    }


def build_running_total_series(values):
    running = 0.0
    out = []
    for value in values or ():
        running += float(value or 0.0)
        out.append(running)
    return out


def resample_discrete_series(values, target_count):
    n = int(target_count or 0)
    if n <= 0:
        return []

    src = [float(v or 0.0) for v in (values or [])]
    if not src:
        return [0.0] * n
    if len(src) == 1:
        return [src[0]] * n

    last = len(src) - 1
    out = []
    for i in range(n):
        pos = (i * last) / max(1, n - 1)
        lo = int(pos)
        hi = min(last, lo + 1)
        frac = pos - lo
        out.append(src[lo] + ((src[hi] - src[lo]) * frac))
    return out


def build_default_line_x_positions(margin_left, plot_w, points_count):
    count = int(points_count or 0)
    if count > 1:
        return [margin_left + (plot_w * i / (count - 1)) for i in range(count)]
    return [margin_left + (plot_w * 0.5)]


def build_cumulative_points(x_positions, cumulative_values, *, margin_top, plot_h, line_total):
    points = []
    denom = max(1.0, float(line_total or 0.0))
    for i, x in enumerate(x_positions or ()):
        cum_v = cumulative_values[i] if i < len(cumulative_values) else 0.0
        y = margin_top + plot_h - (float(cum_v or 0.0) / denom * plot_h)
        points.append((float(x), float(y)))
    return points


def build_cumulative_paths(points, *, margin_top, plot_h):
    if not points:
        return None, None

    path = QPainterPath()
    path.moveTo(points[0][0], points[0][1])
    add_smooth_line(path, [QPointF(x, y) for x, y in points])

    fill_path = QPainterPath(path)
    fill_path.lineTo(points[-1][0], margin_top + plot_h)
    fill_path.lineTo(points[0][0], margin_top + plot_h)
    fill_path.closeSubpath()
    return path, fill_path


def resolve_discrete_bar_draw_state(
    widget,
    *,
    plot_w,
    points_count,
    margin_left,
    t,
    width_ratio,
    transition_count_attr="points_count",
):
    count = int(points_count or 0)
    step_x = plot_w / count if count > 0 else plot_w
    bar_w = max(1.0, step_x * float(width_ratio or 0.0))
    slots = None
    if widget._data_transition_active:
        old_attr, new_attr = _resolve_transition_count_attrs(transition_count_attr)
        old_count = int(getattr(widget, old_attr, 0) or 0)
        new_count = int(getattr(widget, new_attr, 0) or 0)
        slots = widget.interpolate_bar_slots(
            old_count,
            new_count,
            t,
            margin_left,
            plot_w,
            align_right=widget._transition_align_right,
            width_ratio=float(width_ratio or 0.0),
        )
    intro = 1.0 if widget._data_transition_active else max(0.0, min(1.0, float(t)))
    return step_x, bar_w, slots, intro


def resolve_discrete_bar_geometry(index, *, step_x, bar_w, slots, margin_left):
    if slots and index < len(slots):
        center_x, slot_w = slots[index]
        cur_w = max(1.0, slot_w)
        x = center_x - (cur_w / 2.0)
        return x, cur_w
    cur_w = max(1.0, float(bar_w or 0.0))
    x = margin_left + (index * step_x) + (step_x - cur_w) / 2.0
    return x, cur_w


def build_discrete_gradient_color(base_color, *, ratio, dark):
    c = QColor(base_color)
    clamped_ratio = max(0.0, min(1.0, float(ratio or 0.0)))
    light_mul = 1.4 if dark else 1.22
    dark_mul = 0.7 if dark else 0.68
    start_l = min(255, int(c.lightness() * light_mul))
    end_l = max(0, int(c.lightness() * dark_mul))
    current_l = int(start_l - (start_l - end_l) * clamped_ratio)
    c.setHsl(c.hslHue(), c.hslSaturation(), current_l)
    return c


def finalize_discrete_bar_color(color, *, dark, hovered, opacity_pct):
    c = QColor(color)
    if hovered:
        c = c.lighter(130) if dark else c.darker(115)
        c.setAlpha(255)
    else:
        c.setAlpha(int(float(opacity_pct or 0.0) * 2.55))
    return c


def finalize_discrete_transition_state(widget, *, t=None, count_attr="points_count"):
    progress = widget.get_progress() if t is None else t
    if not (widget._data_transition_active and progress >= 0.999):
        return False

    from .data import reset_discrete_transition_state

    reset_discrete_transition_state(widget, count_attr=count_attr)
    return True
