# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QColor, QPointF, QRect, QRectF

from ...chart_utils import ChartGeometry


def recalculate_layout_impl(widget):
    w = widget.width()
    h = widget.height()
    if w < 10 or h < 10:
        return

    widget.bar_rects = []
    widget.group_labels_rects = []

    groups = ["learning", "young", "mature"]
    n_groups = len(groups)

    fm = widget.fontMetrics()
    margin_top = ChartGeometry.MARGIN_TOP
    margin_bottom = ChartGeometry.MARGIN_BOTTOM
    margin_left = ChartGeometry.calculate_dynamic_left_margin(fm, widget.max_val)
    margin_right = ChartGeometry.DEFAULT_MARGIN_RIGHT

    widget.margins = (margin_left, margin_top, margin_right, margin_bottom)

    avail_w = w - margin_left - margin_right
    avail_h = h - margin_top - margin_bottom

    group_width = avail_w / n_groups
    bar_spacing = 4
    group_padding = 20
    bar_w = (group_width - group_padding * 2 - (len(widget.colors) - 1) * bar_spacing) / len(widget.colors)
    if bar_w < 2:
        bar_w = 2

    for i, group_key in enumerate(groups):
        group_x = margin_left + (i * group_width)
        label_rect = QRect(int(group_x), h - margin_bottom + 5, int(group_width), 20)
        widget.group_labels_rects.append((label_rect, widget.group_labels.get(group_key, group_key)))

        values = widget.data.get(group_key, [0, 0, 0, 0])
        start_x = group_x + group_padding
        for b_idx, val in enumerate(values):
            x = start_x + (b_idx * (bar_w + bar_spacing))
            bar_h_full = (val / widget.max_val) * avail_h if widget.max_val > 0 else 0
            rect = QRectF(x, margin_top + avail_h - bar_h_full, bar_w, bar_h_full)
            widget.bar_rects.append(
                {
                    "group": group_key,
                    "btn_idx": b_idx,
                    "val": val,
                    "rect": rect,
                    "color": QColor(widget.colors[b_idx]),
                }
            )


def get_bar_at_pos_impl(widget, pos):
    if not pos:
        return None
    for bar in widget.bar_rects:
        full_rect = bar["rect"]
        hit_rect = full_rect.adjusted(-2, 0, 2, 0)
        margin_left, margin_top, margin_right, margin_bottom = widget.margins
        hit_rect.setBottom(widget.height() - margin_bottom)
        hit_rect.setTop(margin_top)
        if hit_rect.contains(QPointF(pos)):
            return bar
    return None
