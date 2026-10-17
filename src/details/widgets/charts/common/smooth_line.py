# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Slightly rounded polyline for cumulative ("Total") lines."""


def add_smooth_line(path, points, smoothing=1.0):
    """Append segments to path (already at points[0]) with softened corners.

    Catmull-Rom style tangents scaled by smoothing (1.0 = full). Control points
    stay between the neighbouring y values, so a rising total never dips or
    overshoots and flat days stay flat.
    """
    n = len(points)
    if n < 3:
        for p in points[1:]:
            path.lineTo(p)
        return
    k = smoothing / 6.0
    # x and y read once per point (a QPointF call costs more than the arithmetic around it)
    xs = [p.x() for p in points]
    ys = [p.y() for p in points]
    last = n - 1
    cubic = path.cubicTo
    for i in range(last):
        j = i - 1 if i > 0 else i
        q = i + 2 if i + 2 < n else i + 1
        x1, y1, x2, y2 = xs[i], ys[i], xs[i + 1], ys[i + 1]
        lo, hi = (y1, y2) if y1 <= y2 else (y2, y1)
        c1y = min(hi, max(lo, y1 + (y2 - ys[j]) * k))
        c2y = min(hi, max(lo, y2 - (ys[q] - y1) * k))
        c1x = x1 + (x2 - xs[j]) * k
        c2x = x2 - (xs[q] - x1) * k
        c1x = min(x2, max(x1, c1x))
        c2x = min(x2, max(x1, c2x))
        cubic(c1x, c1y, c2x, c2y, x2, y2)
