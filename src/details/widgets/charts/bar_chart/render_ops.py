# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QColor, QPainter, QRectF, Qt


def paint_event_impl(widget, event):
    if not widget.data:
        return
    intro_t = max(0.0, min(1.0, float(widget.get_progress())))
    values = widget.normalized_values()

    painter = QPainter(widget)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)

    width = widget.width()
    height = widget.height()
    padding_x = 4
    padding_y = 6
    effective_w = width - (padding_x * 2)
    effective_h = height - (padding_y * 2)

    max_val = max(values) if values else 0
    if max_val == 0:
        max_val = 1
    n = len(values)
    if n == 0:
        return
    bar_w = (effective_w / n) * 0.8
    if bar_w < 1:
        bar_w = 1

    base_alpha = int(getattr(widget, "chart_opacity_pct", 100) * 2.55)
    x = padding_x
    step_x = effective_w / n
    for val in values:
        bar_h = (val / max_val) * effective_h * intro_t
        y = (height - padding_y) - bar_h

        color = QColor(widget.color)
        if val == 0:
            color.setAlpha(0)
        else:
            color.setAlpha(int(base_alpha * intro_t))

        painter.setBrush(color)
        painter.drawRoundedRect(QRectF(x, y, bar_w, bar_h), 2, 2)
        x += step_x
