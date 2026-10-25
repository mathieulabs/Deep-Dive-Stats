# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import math
from datetime import datetime, timedelta

from aqt.qt import QBrush, QColor, QRectF

from ....ui import Config, rollover_hour, get_chart_color
from ...chart_utils import is_night_mode
from .metrics import entry_counts


def color_token_impl(widget, color):
    try:
        if isinstance(color, QColor):
            return int(color.rgba())
        return int(QColor(color).rgba())
    except Exception:
        return str(color)


def brush_for_color_impl(widget, color):
    token = color_token_impl(widget, color)
    cache = getattr(widget, "_color_brush_cache", None)
    if cache is None:
        cache = {}
        widget._color_brush_cache = cache
    brush = cache.get(token)
    if brush is None:
        brush = QBrush(QColor(color))
        cache[token] = brush
    return brush


def is_empty_cell_color_impl(widget, color):
    empty = widget.empty_color
    if color is empty:
        return True
    return color_token_impl(widget, color) == color_token_impl(widget, empty)


def lerp_color_impl(widget, c1, c2, t):
    a1 = float(c1.alpha())
    a2 = float(c2.alpha())
    a = widget._lerp(a1, a2, t)
    if a <= 0.001:
        return QColor(0, 0, 0, 0)

    r_pm = widget._lerp(float(c1.red()) * a1, float(c2.red()) * a2, t)
    g_pm = widget._lerp(float(c1.green()) * a1, float(c2.green()) * a2, t)
    b_pm = widget._lerp(float(c1.blue()) * a1, float(c2.blue()) * a2, t)

    r = max(0, min(255, int(round(r_pm / a))))
    g = max(0, min(255, int(round(g_pm / a))))
    b = max(0, min(255, int(round(b_pm / a))))
    return QColor(r, g, b, max(0, min(255, int(round(a)))))


def resolve_cell_color_impl(widget, count, future, curr_date_val, logical_today, max_past_count, max_future_count):
    is_future = curr_date_val > logical_today
    is_today = curr_date_val == logical_today

    if is_future:
        if widget.show_future and future > 0:
            level = widget._future_level_index(future, max_future_count)
            return widget.future_levels[level]
        return widget.empty_color

    if is_today and count == 0 and future > 0 and widget.show_future:
        level = widget._future_level_index(future, max_future_count)
        return widget.future_levels[level]

    if count == 0:
        return widget.empty_color

    hidden = getattr(widget, "hidden_legend_steps", None)
    if hidden:
        # A legend range switched off by clicking it: those days look empty.
        from .legend import step_for_level

        if step_for_level(widget, past_level_index_impl(widget, count, max_past_count)) in hidden:
            return widget.empty_color

    return past_level_color_impl(widget, count, max_past_count)


def past_level_index_impl(widget, count, max_past_count):
    curve = 65.0 / widget.intensity_curve
    return min(widget.color_levels - 1, int(((count / max_past_count) ** curve) * widget.color_levels))


def past_level_color_impl(widget, count, max_past_count):
    level = past_level_index_impl(widget, count, max_past_count)
    color = widget.levels[level]
    ratio = count / max_past_count
    if ratio <= 1.0 or level < widget.color_levels - 1:
        return color
    # Days far above the scale (beyond the 95th percentile) keep going: lighter on a
    # dark theme, darker on a light one, up to 4x the scale.
    t = min(1.0, math.log2(ratio) / 2.0)
    hue, sat, light, alpha = color.getHsl()
    shift = int(255 * 0.16 * t)
    lighter = is_night_mode(widget) != bool(getattr(widget, "invert_intensity", False))
    light = min(255, light + shift) if lighter else max(0, light - shift)
    boosted = QColor.fromHsl(max(0, hue), sat, light)
    boosted.setAlpha(alpha)
    return boosted


def future_level_index_impl(widget, future, max_future_count):
    curve = 65.0 / widget.intensity_curve
    denom = max(1.0, float(max_future_count or 0.0))
    level = min(widget.color_levels - 1, int(((float(future) / denom) ** curve) * widget.color_levels))
    if future > 0 and widget.color_levels > 1:
        level = max(1, level)
    return level


def build_current_cell_visuals_impl(widget, data_source=None):
    if data_source is None:
        data_source = widget.data

    visuals = {}
    max_past_count, max_future_count = widget._get_max_counts(data_source)
    offset_h = rollover_hour()
    logical_today = (datetime.now() - timedelta(hours=offset_h)).date()

    if widget.view_mode == "continuous":
        cell_size, spacing, step, gap_width, label_space, margin_top, start_x, months_list = widget._get_continuous_layout()
        current_x = start_x
        for (_yr, _mo, start_col, num_cols, days_in_month, first_day) in months_list:
            for col in range(num_cols):
                for row in range(7):
                    day_offset = col * 7 + row - start_col
                    if day_offset < 0 or day_offset >= days_in_month:
                        continue
                    curr_date = first_day + timedelta(days=day_offset)
                    date_str = curr_date.isoformat()[:10]
                    entry = data_source.get(date_str, 0)
                    count, future = entry_counts(widget, entry)
                    color = widget._resolve_cell_color(count, future, curr_date.date(), logical_today, max_past_count, max_future_count)
                    x = current_x + (col * step)
                    y = margin_top + (row * step)
                    visuals[date_str] = (QRectF(x, y, cell_size, cell_size), QColor(color))
            current_x += num_cols * step + gap_width
        return visuals

    cell_size, spacing, start_x, start_y, _label_space = widget._get_grid_geometry()
    step = cell_size + spacing
    grid_start, in_range = widget._compute_grid_info()
    for week in range(53):
        week_x = start_x + (week * step)
        for day in range(7):
            curr_date = grid_start + timedelta(weeks=week, days=day)
            if not in_range(curr_date):
                continue
            date_str = curr_date.isoformat()[:10]
            entry = data_source.get(date_str, 0)
            count, future = entry_counts(widget, entry)
            color = widget._resolve_cell_color(count, future, curr_date.date(), logical_today, max_past_count, max_future_count)
            y = start_y + (day * step)
            visuals[date_str] = (QRectF(week_x, y, cell_size, cell_size), QColor(color))
    return visuals


def visual_delta_ratio_impl(widget, old_data, new_data):
    keys = set(old_data.keys()) | set(new_data.keys())
    if not keys:
        return 0.0
    old_sum = 0.0
    new_sum = 0.0
    delta_sum = 0.0
    for k in keys:
        orv, ofv = widget._entry_counts(old_data, k)
        nrv, nfv = widget._entry_counts(new_data, k)
        old_v = max(0.0, orv) + max(0.0, ofv)
        new_v = max(0.0, nrv) + max(0.0, nfv)
        old_sum += old_v
        new_sum += new_v
        delta_sum += abs(new_v - old_v)
    denom = max(old_sum + new_sum, 1.0)
    return delta_sum / denom


def refresh_data_colors_impl(widget):
    widget.base_color = QColor(get_chart_color(Config.HEATMAP_COLOR, widget))
    widget._update_levels()


def update_levels_impl(widget):
    max_alpha = int(widget.filled_opacity_pct * 2.55)

    # Levels only depend on these inputs. update_styles() re-applies them after
    # every pinned rebuild, so skip the work (and keep the rendered heatmap) when
    # nothing changed.
    try:
        sig = (
            QColor(widget.base_color).rgba(),
            int(widget.filled_opacity_pct),
            widget.vibrance,
            widget.color_levels,
            bool(widget.multi_hue_intensity),
            bool(widget.tinted_future),
            bool(is_night_mode(widget)),
            bool(getattr(widget, "invert_intensity", False)),
        )
    except Exception:
        sig = None
    if sig is not None and sig == getattr(widget, "_levels_sig", None) and getattr(widget, "levels", None):
        return
    widget._levels_sig = sig

    def _l(pct):
        return max(0, min(255, int(round((pct / 100.0) * 255.0))))

    def _lerp_hue(h0, h1, t):
        if h0 < 0 and h1 < 0:
            return 0
        if h0 < 0:
            return int(h1)
        if h1 < 0:
            return int(h0)
        delta = ((h1 - h0 + 180) % 360) - 180
        return int((h0 + (delta * t)) % 360)

    widget.levels = []
    widget.future_levels = []
    is_dark = is_night_mode(widget)

    base_c = QColor(widget.base_color)
    h = base_c.hue()
    s = base_c.saturation()

    vib_factor = widget.vibrance / 100.0
    s = max(0, min(255, int(s * vib_factor)))

    l = base_c.lightness()

    steps = widget.color_levels
    if widget.multi_hue_intensity:
        start_h = (h - 34) % 360 if h >= 0 else 0
        end_h = (h + 8) % 360 if h >= 0 else 0
        if is_dark:
            start_l = _l(56)
            end_l = max(_l(74), l)
        else:
            start_l = _l(86)
            end_l = max(_l(62), min(l, _l(78)))
        start_s = max(70, int(s * 0.7))
        end_s = min(255, max(120, int(s * 1.05)))

        for i in range(steps):
            t = i / (steps - 1)
            hh = _lerp_hue(start_h, end_h, t)
            ss = int(start_s + ((end_s - start_s) * t))
            ll = int(start_l + ((end_l - start_l) * t))
            c = QColor.fromHsl(hh, ss, ll)
            c.setAlpha(max_alpha)
            widget.levels.append(c)
    else:
        if is_dark:
            # HSL lightness is 0-255 here; 40 was nearly black on a dark card.
            start_l = _l(46)
            end_l = max(l, _l(70))
        else:
            # 97% was almost white: the lightest days vanished on a white card.
            start_l = _l(84)
            end_l = min(l, _l(52))

        for i in range(steps):
            t = i / (steps - 1)
            new_l = int(start_l + t * (end_l - start_l))
            c = QColor.fromHsl(h, s, new_l)
            c.setAlpha(max_alpha)
            widget.levels.append(c)

    if getattr(widget, "invert_intensity", False):
        widget.levels.reverse()

    if widget.tinted_future:
        hg = h
        sg = int(s * 0.2)
    else:
        base_gray = QColor(128, 128, 128)
        hg = base_gray.hue()
        sg = base_gray.saturation()

    if is_dark:
        start_lg, end_lg = 56, 150
    else:
        start_lg, end_lg = _l(82), _l(48)

    for i in range(steps):
        t = i / (steps - 1)
        new_l = int(start_lg + t * (end_lg - start_lg))
        c = QColor.fromHsl(hg, sg, new_l)
        c.setAlpha(max_alpha)
        widget.future_levels.append(c)

    widget._pixmap_cache = None
    widget._transition_new_pixmap = None
    widget.update()


def update_empty_color_impl(widget):
    is_dark = is_night_mode(widget)
    opacity = int(widget.current_opacity_pct * 2.55)

    if is_dark:
        col = QColor(255, 255, 255, opacity) if widget.empty_white else QColor(0, 0, 0, opacity)
    else:
        if widget.empty_white:
            col = QColor(255, 255, 255, opacity)
        else:
            gray_alpha = max(18, min(110, int(opacity * 0.7)))
            col = QColor(132, 132, 132, gray_alpha)

    prev = getattr(widget, "empty_color", None)
    if isinstance(prev, QColor) and prev.rgba() == col.rgba():
        # unchanged; keep the cached scaffold/cell pixmaps.
        return
    widget.empty_color = col
    widget._scaffold_pixmap_cache = None
    widget._scaffold_pixmap_cache_key = None
    widget._pixmap_cache = None
    widget._transition_new_pixmap = None
    widget.update()
