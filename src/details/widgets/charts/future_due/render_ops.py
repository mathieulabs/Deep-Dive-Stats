# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..common.cache_dpr import cache_dpr, cache_surface, draw_cache, stale_cache
from aqt.qt import QColor, QPainter, QPen, QPointF, QRectF, Qt

from ...chart_utils.drawing import chart_style, draw_bar_rect, draw_right_axis_labels, get_hover_marker_outline_color
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


def _draw_cached_chrome(widget, painter, *, width, height, plot_w, plot_h, margin_left, margin_top, margin_right, margin_bottom, draw_values, total_cards):
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
        int(margin_right),
        int(margin_bottom),
        int(getattr(widget, "max_days", 0) or 0),
        int(getattr(widget, "_points_count", 0) or 0),
        int(getattr(widget, "_get_min_day", lambda: 0)() or 0),
        bool(getattr(widget, "show_backlog", False)),
        _series_cache_token(draw_values),
        int(round(float(total_cards or 0.0))),
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
                widget.draw_cumulative_area(cp, plot_w, plot_h, margin_left, margin_top, total_cards)
            widget.draw_x_axis(cp, plot_w, height, margin_left, margin_top, margin_bottom)
            widget.draw_stats_text(cp, plot_w, height, margin_left, margin_bottom)
            if getattr(widget, "show_cumulative_axis", True):
                draw_right_axis_labels(
                    cp,
                    width,
                    height,
                    margin_right,
                    margin_top,
                    margin_bottom,
                    total_cards,
                    widget=widget,
                )
        finally:
            cp.end()
        widget._chrome_cache_key = cache_key
        widget._chrome_cache_pixmap = px
        pixmap = px

    if pixmap is not None:
        draw_cache(painter, pixmap)


def paint_event_impl(widget, event):
    # An empty deck still draws its (empty) axes, like the other charts.
    painter = QPainter(widget)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    w = widget.width()
    h = widget.height()

    state = prepare_discrete_paint_state(widget, painter)
    t = state["t"]
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
        max_cumulative=None,
    )
    if draw_values:
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
            margin_right=margin_right,
            margin_bottom=margin_bottom,
            draw_values=draw_values,
            total_cards=total_cards,
        )
    else:
        if draw_values and getattr(widget, "cumulative_visible", True):
            widget.draw_cumulative_area(painter, plot_w, plot_h, margin_left, margin_top, total_cards)
        widget.draw_x_axis(painter, plot_w, h, margin_left, margin_top, margin_bottom)
        widget.draw_stats_text(painter, plot_w, h, margin_left, margin_bottom)
        if getattr(widget, "show_cumulative_axis", True):
            draw_right_axis_labels(
                painter,
                w,
                h,
                margin_right,
                margin_top,
                margin_bottom,
                total_cards,
                widget=widget,
            )

    _draw_hover_dots(widget, painter)
    finalize_discrete_transition_state(widget, t=t)


def _draw_hover_dots(widget, painter):
    """Breakdown by Type: a dot in the middle of each type of the hovered bar, as on
    Activity's breakdown (collected by draw_bars_impl)."""
    dots = getattr(widget, "_hover_type_dots", None)
    if not dots or int(getattr(widget, "hover_index", -1)) == -1:
        return
    outline = get_hover_marker_outline_color(widget)
    outline.setAlpha(230 if is_night_mode(widget) else 210)
    painter.setPen(QPen(outline, 1.5))
    for center, color in dots:
        painter.setBrush(color)
        painter.drawEllipse(center, 4, 4)


def draw_bars_impl(widget, painter, plot_w, plot_h, margin_left, margin_top):
    draw_values = getattr(widget, "_anim_draw_values", widget._display_values)
    draw_ratios = getattr(widget, "_anim_draw_ratios", [])
    points_count = int(getattr(widget, "_anim_draw_points_count", widget._points_count) or 0)
    if points_count <= 0:
        return

    base_color = QColor(widget.bar_color)
    from ....ui import Config, get_chart_color
    backlog_color = QColor(get_chart_color(Config.COLOR_BACKLOG, widget))
    dark = is_night_mode(widget)
    t = widget.get_progress()
    step_x, bar_w, slots, intro = resolve_discrete_bar_draw_state(
        widget,
        plot_w=plot_w,
        points_count=points_count,
        margin_left=margin_left,
        t=t,
        width_ratio=0.9,
    )

    # While bars move between two datasets, a bar's backlog colour fades between what it was
    # and what it becomes (instead of every orange bar turning blue at once).
    backlog_weight = None
    flags = getattr(widget, "_backlog_flags", None)
    if widget._data_transition_active and flags is not None:
        old_f, new_f = flags
        n = max(len(old_f), len(new_f))
        if getattr(widget, "_transition_align_right", False):
            old_f = [False] * (n - len(old_f)) + list(old_f)
            new_f = [False] * (n - len(new_f)) + list(new_f)
        else:
            old_f = list(old_f) + [False] * (n - len(old_f))
            new_f = list(new_f) + [False] * (n - len(new_f))
        p = max(0.0, min(1.0, float(t)))
        backlog_weight = [(1.0 - p) * float(a) + p * float(b) for a, b in zip(old_f, new_f)]

    # "Breakdown by Type": the bars split into mature / young / learning. During a
    # transition the shares glide from the old bars' to the new ones', and a bar going from
    # plain to split (or back) fades between its plain colour and the type colours.
    transition = bool(widget._data_transition_active)
    if transition:
        old_sh, new_sh = getattr(widget, "_type_shares", (None, None))
    else:
        # Read again from the data: the bars may have been binned again since (a resize).
        # Kept while the data and the binning stay the same (it was worked out on every
        # paint, bar by bar).
        from .data_ops import type_shares

        old_sh = None
        dist = widget.data_dict.get("distribution", {})
        memo_key = (id(widget.data_dict), id(dist), id(widget.data_dict.get("breakdown")), widget.max_days,
                    points_count, bool(widget.show_backlog))
        memo = getattr(widget, "_type_shares_memo", None)
        if memo is not None and memo[0] == memo_key:
            new_sh = memo[1]
        else:
            new_sh = type_shares(widget, widget.data_dict, dist, widget.max_days, points_count)
            widget._type_shares_memo = (memo_key, new_sh)
    old_kind, old_sh = old_sh if old_sh else (None, None)
    new_kind, new_sh = new_sh if new_sh else (None, None)
    if old_kind is not None and new_kind is not None and old_kind != new_kind:
        old_sh = None  # another breakdown: from plain bars (the colours fade in)
    split_on = new_sh is not None or old_sh is not None
    if split_on:
        from .data_ops import breakdown_parts

        type_colors = [QColor(get_chart_color(c, widget)) for _id, _label, c in breakdown_parts(new_kind or old_kind)]
        p_t = max(0.0, min(1.0, float(t))) if transition else 1.0

        def _align(lst):
            if lst is None:
                return [None] * points_count
            lst = list(lst)
            if len(lst) < points_count:
                pad = [(0.0, 0.0, 0.0)] * (points_count - len(lst))
                lst = (pad + lst) if getattr(widget, "_transition_align_right", False) else (lst + pad)
            return lst

        olds = _align(old_sh)
        news = _align(new_sh)
        # The mix of the whole chart, for a bar shrinking away that has no cards of its own.
        mix = [0.0, 0.0, 0.0]
        for sh in (news if any(x for x in news if x) else olds):
            if sh:
                for k in range(3):
                    mix[k] += sh[k]
        mix = tuple(v / sum(mix) for v in mix) if sum(mix) else (0.0, 0.0, 1.0)

    widget._hover_type_dots = []
    painter.setPen(Qt.PenStyle.NoPen)
    for i in range(points_count):
        bucket_sum = draw_values[i] if i < len(draw_values) else 0.0
        if bucket_sum == 0:
            continue

        x, cur_w = resolve_discrete_bar_geometry(
            i,
            step_x=step_x,
            bar_w=bar_w,
            slots=slots,
            margin_left=margin_left,
        )
        ratio_for_height = draw_ratios[i] if i < len(draw_ratios) else (bucket_sum / max(1.0, widget.max_val))
        bar_h = ratio_for_height * plot_h * intro
        y = margin_top + plot_h - bar_h
        bar_center_x = x + (cur_w / 2.0)

        so = olds[i] if split_on and i < len(olds) else None
        sn = news[i] if split_on and i < len(news) else None
        if so is not None or sn is not None:
            a_sh = so if so is not None and any(so) else None
            b_sh = sn if sn is not None and any(sn) else None
            a_sh = a_sh or b_sh or mix
            b_sh = b_sh or a_sh
            parts = tuple((1.0 - p_t) * a_sh[k] + p_t * b_sh[k] for k in range(3))
            # How much the type colours show: 0 = a plain bar, 1 = split.
            w_split = (1.0 - p_t) * (so is not None) + p_t * (sn is not None)
            if w_split < 1.0:
                ratio = (bar_center_x - margin_left) / max(1.0, float(plot_w))
                plain_c = build_discrete_gradient_color(base_color, ratio=ratio, dark=dark)
            whole = float(sum(parts)) or 1.0
            top = max((k for k, v in enumerate(parts) if v > 1e-6), default=2)
            # The upper parts first, each lower one reaching a little into the one above:
            # no seam between two parts (a full overlap would show with a see-through opacity).
            bottom = margin_top + plot_h
            whole_rect = QRectF(x, bottom - bar_h, cur_w, bar_h)
            tops = []
            acc = 0.0
            for v in parts:
                acc += v
                tops.append(bottom - bar_h * (acc / whole))
            for k in range(2, -1, -1):
                if parts[k] <= 1e-6:
                    continue
                tc = type_colors[k]
                if w_split < 1.0:
                    tc = QColor(
                        int(round(plain_c.red() + (tc.red() - plain_c.red()) * w_split)),
                        int(round(plain_c.green() + (tc.green() - plain_c.green()) * w_split)),
                        int(round(plain_c.blue() + (tc.blue() - plain_c.blue()) * w_split)),
                    )
                c = finalize_discrete_bar_color(
                    tc,
                    dark=dark,
                    hovered=(i == widget.hover_index),
                    opacity_pct=getattr(widget, "chart_opacity_pct", 100),
                )
                painter.setBrush(c)
                seg_bottom = bottom
                for j in range(k - 1, -1, -1):
                    if parts[j] > 1e-6:
                        seg_bottom = tops[j]
                        break
                seg_top = tops[k] if k == top else tops[k] - 0.75
                rect = QRectF(x, seg_top, cur_w, max(0.0, seg_bottom - seg_top))
                if i == widget.hover_index and getattr(widget, "show_hover_marker", True):
                    widget._hover_type_dots.append(
                        (QPointF(bar_center_x, (tops[k] + seg_bottom) / 2.0), QColor(tc)))
                # The fade of the whole bar (as a plain bar's), not one per part.
                draw_bar_rect(painter, rect, widget=widget, fade_rect=whole_rect, rounded=(k == top))
            continue

        if backlog_weight is not None and i < len(backlog_weight):
            w = backlog_weight[i]
            ratio = (bar_center_x - margin_left) / max(1.0, float(plot_w))
            c = build_discrete_gradient_color(base_color, ratio=ratio, dark=dark)
            if w > 0.0:
                c = QColor(
                    int(round(c.red() + (backlog_color.red() - c.red()) * w)),
                    int(round(c.green() + (backlog_color.green() - c.green()) * w)),
                    int(round(c.blue() + (backlog_color.blue() - c.blue()) * w)),
                    int(round(c.alpha() + (backlog_color.alpha() - c.alpha()) * w)),
                )
        elif widget._get_bin_day_range(i, points_count)[0] < 0:  # only asked here (a backlog bar)
            c = QColor(backlog_color)
        else:
            ratio = (bar_center_x - margin_left) / max(1.0, float(plot_w))
            c = build_discrete_gradient_color(base_color, ratio=ratio, dark=dark)
        c = finalize_discrete_bar_color(
            c,
            dark=dark,
            hovered=(i == widget.hover_index),
            opacity_pct=getattr(widget, "chart_opacity_pct", 100),
        )

        painter.setBrush(c)
        draw_bar_rect(painter, QRectF(x, y, cur_w, bar_h), widget=widget)


def draw_x_axis_impl(widget, painter, plot_w, total_h, margin_left, margin_top, margin_bottom):
    painter.setPen(get_theme_colors(widget).get("text_secondary", QColor("#888888")))
    font = painter.font()
    font.setPixelSize(10)
    painter.setFont(font)

    min_day = widget._get_min_day()
    points_count = widget._get_points_count()
    step_x = plot_w / points_count if points_count > 0 else plot_w
    last_label = None
    for i in range(0, 6):
        if points_count <= 0:
            break
        idx = int(i / 5.0 * (points_count - 1))
        day, _ = widget._get_bin_day_range(idx, points_count)
        label = f"{day}"
        if label == last_label:
            continue
        last_label = label
        x = margin_left + (idx * step_x) + (step_x / 2)
        t_rect = QRectF(x - 20, total_h - margin_bottom + 5, 40, 15)
        painter.drawText(t_rect, Qt.AlignmentFlag.AlignCenter, label)

    if min_day < 0:
        zero_idx = None
        for i in range(points_count):
            d_start, _ = widget._get_bin_day_range(i, points_count)
            if d_start >= 0:
                zero_idx = i
                break
        if zero_idx is not None:
            zero_x = margin_left + zero_idx * step_x
            saved_pen = painter.pen()
            dashed = QPen(get_theme_colors(widget).get("text_secondary", QColor("#888888")))
            dashed.setStyle(Qt.PenStyle.DashLine)
            dashed.setWidthF(0.8)
            painter.setPen(dashed)
            painter.drawLine(int(zero_x), margin_top, int(zero_x), int(total_h - margin_bottom))
            painter.setPen(saved_pen)


def draw_stats_text_impl(widget, painter, plot_w, h, margin_left, margin_bottom):
    return draw_chart_bottom_stats(widget, painter, plot_w, h, margin_left, margin_bottom)
