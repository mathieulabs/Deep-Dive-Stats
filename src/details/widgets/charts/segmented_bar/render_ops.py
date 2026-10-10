# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QColor, QPainter, QPainterPath, QRectF, Qt


def paint_event_impl(widget, event):
    total = sum(widget.counts)
    if total == 0:
        return

    painter = QPainter(widget)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    width = widget.width()
    height = widget.height()
    radius = 4

    path = QPainterPath()
    path.addRoundedRect(0, 2, width, height - 4, radius, radius)
    painter.fillPath(path, QColor(60, 60, 60, 30))

    x = 0
    full_rect = QRectF(0, 2, width, height - 4)

    painter.save()
    clip_path = QPainterPath()
    clip_path.addRoundedRect(full_rect, radius, radius)
    painter.setClipPath(clip_path)

    for i, count in enumerate(widget.counts):
        if count == 0:
            continue
        part = count / total
        seg_w = (width * part) * widget._progress

        color = QColor(widget.colors[i])
        color.setAlpha(180)
        painter.fillRect(QRectF(x, 2, seg_w, height - 4), color)
        x += (width * part) * widget._progress

    painter.restore()

    text = getattr(widget, "center_text", None)
    if text:
        try:
            from ...chart_utils.theme import get_theme_colors

            # The bar colors are medium tones: near black on light themes and near
            # white on dark ones stays readable on both the green and the red part.
            is_dark = bool(get_theme_colors(widget).get("is_dark", True))
            pen_color = QColor("#f5f5f5") if is_dark else QColor("#1b1b1f")
        except Exception:
            pen_color = QColor(245, 245, 245)
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(pen_color)
        painter.drawText(full_rect, Qt.AlignmentFlag.AlignCenter, text)
