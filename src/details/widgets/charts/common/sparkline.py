# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import (
    QWidget, Qt, QColor, QPainter, QPainterPath, QPen, QSize
)

class SparklineWidget(QWidget):
    def __init__(self, data, parent=None, color="#8ab4f8"):
        super().__init__(parent)
        self.data = data
        self.color = QColor(color)
        self.setMinimumWidth(50)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.doubleClicked = None

    def sizeHint(self):
        return QSize(100, 24)

    def paintEvent(self, event):
        if not self.data:
            return

        values = []
        for d in self.data:
            if isinstance(d, (list, tuple)) and len(d) == 2:
                values.append(d[1])
            else:
                values.append(d)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        padding_x = 4
        padding_y = 6

        effective_w = width - (padding_x * 2)
        effective_h = height - (padding_y * 2)

        max_val = max(values) if values else 0
        if max_val == 0: max_val = 1

        n = len(values)
        if n < 2:
            return

        x_step = effective_w / (n - 1)

        points = []
        for i, val in enumerate(values):
            x = padding_x + (i * x_step)
            y = (height - padding_y) - (val / max_val * effective_h)
            points.append((x, y))

        area_path = QPainterPath()
        area_path.moveTo(points[0][0], height - padding_y)
        for x, y in points:
            area_path.lineTo(x, y)
        area_path.lineTo(points[-1][0], height - padding_y)
        area_path.closeSubpath()

        fill_grad = QColor(self.color)
        fill_grad.setAlpha(30)
        painter.fillPath(area_path, fill_grad)

        if n > 500:
            weight = 1.0
        elif n > 100:
            weight = 1.2
        else:
            weight = 2.0

        pen = QPen(self.color, weight, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        line_path = QPainterPath()
        line_path.moveTo(points[0][0], points[0][1])
        for x, y in points[1:]:
            line_path.lineTo(x, y)
        painter.drawPath(line_path)

    def mouseDoubleClickEvent(self, event):
        if self.doubleClicked:
            self.doubleClicked()
        super().mouseDoubleClickEvent(event)
