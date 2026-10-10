# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Rounded look for the retention chart: smooth lines and bars with rounded tops."""
from aqt.qt import QPainterPath, QPointF


def tangents(points):
    """Slope at each point for a monotone cubic curve (it never goes past the data)."""
    n = len(points)
    if n < 2:
        return [0.0] * n
    h = [points[i + 1].x() - points[i].x() for i in range(n - 1)]
    d = [
        (points[i + 1].y() - points[i].y()) / h[i] if h[i] else 0.0
        for i in range(n - 1)
    ]
    m = [0.0] * n
    m[0] = d[0]
    m[-1] = d[-1]
    for i in range(1, n - 1):
        if d[i - 1] * d[i] <= 0:
            m[i] = 0.0
            continue
        w1 = 2 * h[i] + h[i - 1]
        w2 = h[i] + 2 * h[i - 1]
        m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    return m


def control_points(p1, p2, m1, m2):
    """The two bezier handles that join p1 to p2 with the given slopes."""
    h = p2.x() - p1.x()
    return (
        QPointF(p1.x() + h / 3.0, p1.y() + m1 * h / 3.0),
        QPointF(p2.x() - h / 3.0, p2.y() - m2 * h / 3.0),
    )


def build_paths(runs, base_y):
    """Line path and area path from runs of consecutive points, with curved joins."""
    path = QPainterPath()
    area = QPainterPath()
    for run in runs:
        if not run:
            continue
        path.moveTo(run[0])
        area.moveTo(run[0].x(), base_y)
        area.lineTo(run[0])
        if len(run) > 1:
            m = tangents(run)
            for i in range(len(run) - 1):
                c1, c2 = control_points(run[i], run[i + 1], m[i], m[i + 1])
                path.cubicTo(c1, c2, run[i + 1])
                area.cubicTo(c1, c2, run[i + 1])
        area.lineTo(run[-1].x(), base_y)
    return path, area


def bar_path(x0, x1, top, bottom, radius=3.0):
    """A bar whose top corners are rounded."""
    r = max(0.0, min(radius, (x1 - x0) / 2.0, bottom - top))
    path = QPainterPath()
    path.moveTo(x0, bottom)
    path.lineTo(x0, top + r)
    path.quadTo(x0, top, x0 + r, top)
    path.lineTo(x1 - r, top)
    path.quadTo(x1, top, x1, top + r)
    path.lineTo(x1, bottom)
    path.closeSubpath()
    return path
