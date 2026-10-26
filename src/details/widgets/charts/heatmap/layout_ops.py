# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from datetime import datetime, timedelta

from aqt.qt import QSize

from ....ui import day_end_with_rollover
from .legend import legend_height
from .metrics import compute_scales, entry_counts


_MAX_GROW = 6.0


def _grow_factor(widget, ratio, unit_h):
    """How much the whole drawing may grow when the card is wider than it needs. The card
    height limits it too, so the 7 rows never get cut. unit_h is the drawing height at
    normal size (without the bottom padding and the legend)."""
    if ratio <= 1.0:
        return 1.0
    g = min(ratio, _MAX_GROW)
    h = widget.height()
    if h > 0 and unit_h > 0:
        fixed = (10 * widget.scale) + legend_height(widget)
        g = min(g, (h - fixed) / unit_h)
    return max(1.0, g)


def compute_grid_info_impl(widget):
    today = widget.end_date
    if widget.view_mode == "year":
        start_date = datetime(today.year, 1, 1)
        wd = start_date.weekday()
        dow = wd if widget.monday_first else (wd + 1) % 7
        grid_start = start_date - timedelta(days=dow)
        yr = today.year
        return grid_start, lambda d: d.year == yr

    range_end = today
    range_start = today - timedelta(days=364)
    wd = range_start.weekday()
    dow = wd if widget.monday_first else (wd + 1) % 7
    grid_start = range_start - timedelta(days=dow)
    rs, re = range_start, range_end
    return grid_start, lambda d: rs <= d <= re


_CONT_BOX_COLS = 48


def get_continuous_months_impl(widget):
    anchor = day_end_with_rollover()
    ref_month = anchor.month + widget.cont_month_offset
    ref_year = anchor.year
    while ref_month > 12:
        ref_month -= 12
        ref_year += 1
    while ref_month < 1:
        ref_month += 12
        ref_year -= 1
    result = []
    for offset in range(-4, 5):
        m = ref_month + offset
        y = ref_year
        while m > 12:
            m -= 12
            y += 1
        while m < 1:
            m += 12
            y -= 1
        first_day = datetime(y, m, 1)
        next_first = datetime(y + 1, 1, 1) if m == 12 else datetime(y, m + 1, 1)
        days_in_month = (next_first - first_day).days
        wd = first_day.weekday()
        start_col = wd if widget.monday_first else (wd + 1) % 7
        num_cols = (start_col + days_in_month + 6) // 7
        result.append((y, m, start_col, num_cols, days_in_month, first_day))
    return result


def get_continuous_layout_impl(widget):
    months = widget._get_continuous_months()
    if widget._cont_layout_cache is None:
        base_cell_size = 14.0
        target_cell_size = base_cell_size * widget.scale

        show_lbl = widget._effective_show_labels
        label_space = (30 * widget.scale) if show_lbl else (2 * widget.scale)
        margin_top = (22 * widget.scale) if show_lbl else (2 * widget.scale)

        spacing = target_cell_size * 0.25
        step = target_cell_size + spacing
        gap_steps = 0.35
        gap_width = gap_steps * step

        actual_cols = _CONT_BOX_COLS
        total_assembly_w = label_space + actual_cols * step + (len(months) - 1) * gap_width

        available_w = widget.width() - 4
        if total_assembly_w > available_w and available_w > 50:
            fit_ratio = available_w / total_assembly_w
            cell_size = target_cell_size * fit_ratio
            spacing = spacing * fit_ratio
            step = step * fit_ratio
            gap_width = gap_width * fit_ratio
            label_space = label_space * fit_ratio
            margin_top = margin_top * fit_ratio
            total_assembly_w = available_w
        else:
            cell_size = target_cell_size
            if available_w > 50 and total_assembly_w > 0:
                g = _grow_factor(
                    widget, available_w / total_assembly_w, margin_top + 7 * step
                )
                if g > 1.0:
                    cell_size *= g
                    spacing *= g
                    step *= g
                    gap_width *= g
                    label_space *= g
                    margin_top *= g
                    total_assembly_w *= g

        if widget.grid_mode:
            content_h = margin_top + 7 * (cell_size + spacing) - spacing + (10 * widget.scale) + legend_height(widget)
            if content_h < widget.height():
                extra_y = (widget.height() - content_h) / 2
                margin_top += extra_y

        extra_offset = 0
        if total_assembly_w < widget.width():
            extra_offset = (widget.width() - total_assembly_w) / 2

        start_x = extra_offset + label_space
        widget._cont_layout_cache = (cell_size, spacing, step, gap_width, label_space, margin_top, start_x)

    cell_size, spacing, step, gap_width, label_space, margin_top, start_x = widget._cont_layout_cache
    # Nine months span 45 to 48 week columns. The box is sized for 48 so it, and the
    # controls lined up with it, stay put while browsing; the grid is centred inside.
    start_x += (_CONT_BOX_COLS - sum(m[3] for m in months)) * step / 2.0
    return cell_size, spacing, step, gap_width, label_space, margin_top, start_x, months


def continuous_hit_test_impl(widget, mx, my):
    cell_size, spacing, step, gap_width, label_space, margin_top, start_x, months = widget._get_continuous_layout()
    start_y = margin_top

    if my < start_y:
        return None
    row = int((my - start_y) / step)
    if row < 0 or row > 6:
        return None

    current_x = start_x
    for (_yr, _mo, start_col, num_cols, days_in_month, first_day) in months:
        block_end_x = current_x + num_cols * step
        if current_x <= mx < block_end_x:
            col = int((mx - current_x) / step)
            day_offset = col * 7 + row - start_col
            if 0 <= day_offset < days_in_month:
                curr_date = first_day + timedelta(days=day_offset)
                return curr_date.isoformat()[:10], curr_date, col, row, current_x
            return None
        current_x = block_end_x + gap_width
    return None


def get_grid_geometry_impl(widget):
    if widget._grid_cache is not None:
        return widget._grid_cache

    base_cell_size = 14.0
    target_cell_size = base_cell_size * widget.scale

    label_space = (30 * widget.scale) if not widget.hide_labels else (2 * widget.scale)
    margin_top = (22 * widget.scale) if not widget.hide_labels else (2 * widget.scale)

    spacing = target_cell_size * 0.25
    grid_width = 53 * (target_cell_size + spacing) - spacing
    total_assembly_w = label_space + grid_width

    available_w = widget.width() - 4
    if total_assembly_w > available_w and available_w > 50:
        fit_ratio = available_w / total_assembly_w
        cell_size = target_cell_size * fit_ratio
        spacing = spacing * fit_ratio
        label_space = label_space * fit_ratio
        margin_top = margin_top * fit_ratio
        total_assembly_w = available_w
    else:
        cell_size = target_cell_size
        if available_w > 50 and total_assembly_w > 0:
            g = _grow_factor(
                widget, available_w / total_assembly_w, margin_top + 7 * (target_cell_size + spacing)
            )
            if g > 1.0:
                cell_size *= g
                spacing *= g
                label_space *= g
                margin_top *= g
                total_assembly_w *= g

    extra_offset = 0
    if total_assembly_w < widget.width():
        extra_offset = (widget.width() - total_assembly_w) / 2

    start_x = extra_offset + label_space
    start_y = margin_top

    if widget.grid_mode:
        content_h = margin_top + 7 * (cell_size + spacing) - spacing + (10 * widget.scale) + legend_height(widget)
        if content_h < widget.height():
            extra_y = (widget.height() - content_h) / 2
            start_y += extra_y

    widget._grid_cache = (cell_size, spacing, start_x, start_y, label_space)
    return widget._grid_cache


def get_max_counts_impl(widget, data_source=None):
    if data_source is None:
        data_source = widget.data
    max_p = 0
    max_f = 0
    past_counts = []
    future_counts = []

    visible_dates = []
    if widget.view_mode == "continuous":
        for (_yr, _mo, _a, _b, days_in_month, first_day) in widget._get_continuous_months():
            for d in range(days_in_month):
                visible_dates.append((first_day + timedelta(days=d)).isoformat()[:10])
    else:
        grid_start, in_range = widget._compute_grid_info()
        for i in range(53 * 7):
            curr = grid_start + timedelta(days=i)
            if in_range(curr):
                visible_dates.append(curr.isoformat()[:10])

    widget._metric_scales = compute_scales(
        widget.metric, [data_source[d] for d in visible_dates if isinstance(data_source.get(d), dict)]
    )
    for d_str in visible_dates:
        entry = data_source.get(d_str)
        if entry:
            p, f = entry_counts(widget, entry)
            if p > 0:
                past_counts.append(p)
            if f > 0:
                future_counts.append(f)
            if p > max_p:
                max_p = p
            if f > max_f:
                max_f = f

    # Scale colors to the 95th percentile so a few huge days don't flatten
    # every other day into the lowest levels. Days above it use the top level.
    if len(past_counts) >= 20:
        past_counts.sort()
        max_p = past_counts[min(len(past_counts) - 1, int(len(past_counts) * 0.95))]
    if len(future_counts) >= 20:
        future_counts.sort()
        max_f = future_counts[min(len(future_counts) - 1, int(len(future_counts) * 0.95))]

    result = (max(1, max_p), max(1, max_f))
    widget._last_max_counts = result  # the legend reads the scale the colors used
    return result


def has_height_for_width_impl(widget):
    return True


def height_for_width_impl(widget, width):
    scale = widget.scale if hasattr(widget, "scale") else 1.0
    base_cell_size = 14.0
    target_cell_size = base_cell_size * scale

    if hasattr(widget, "hide_labels") and widget.hide_labels:
        label_space = 2 * scale
        margin_top = 2 * scale
    else:
        label_space = 30 * scale
        margin_top = 22 * scale

    spacing = target_cell_size * 0.25
    grid_width = 53 * (target_cell_size + spacing) - spacing
    total_assembly_w = label_space + grid_width

    grow = 1.0
    available_w = width - 4
    if total_assembly_w > available_w and available_w > 50:
        fit_ratio = available_w / total_assembly_w
        cell_size = target_cell_size * fit_ratio
        spacing = spacing * fit_ratio
        current_margin = margin_top * fit_ratio
    else:
        cell_size = target_cell_size
        current_margin = margin_top
        if available_w > 50:
            grow = max(1.0, min(available_w / total_assembly_w, _MAX_GROW))
            if grow > 1.0:
                cell_size *= grow
                spacing *= grow
                current_margin *= grow

    req_h = current_margin + 7 * (cell_size + spacing) + (10 * scale) + legend_height(widget)

    if getattr(widget, "grid_mode", False):
        return min(int(180 * grow), int(req_h))

    return int(req_h)


def size_hint_impl(widget):
    scale = widget.scale if hasattr(widget, "scale") else 1.0
    base_cell_size = 14.0
    target_cell_size = base_cell_size * scale
    if widget.hide_labels:
        label_space = 2 * scale
    else:
        label_space = 30 * scale
    spacing = target_cell_size * 0.25
    grid_width = 53 * (target_cell_size + spacing) - spacing
    w = int(label_space + grid_width + 4)
    w = max(150, min(3000, w))
    return QSize(w, widget.heightForWidth(w))


def minimum_size_hint_impl(widget):
    return QSize(200, widget.heightForWidth(200))
