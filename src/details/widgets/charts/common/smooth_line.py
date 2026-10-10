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
    for i in range(n - 1):
        p0 = points[i - 1] if i > 0 else points[i]
        p1 = points[i]
        p2 = points[i + 1]
        p3 = points[i + 2] if i + 2 < n else points[i + 1]
        lo, hi = (p1.y(), p2.y()) if p1.y() <= p2.y() else (p2.y(), p1.y())
        c1y = min(hi, max(lo, p1.y() + (p2.y() - p0.y()) * k))
        c2y = min(hi, max(lo, p2.y() - (p3.y() - p1.y()) * k))
        c1x = p1.x() + (p2.x() - p0.x()) * k
        c2x = p2.x() - (p3.x() - p1.x()) * k
        c1x = min(p2.x(), max(p1.x(), c1x))
        c2x = min(p2.x(), max(p1.x(), c2x))
        path.cubicTo(c1x, c1y, c2x, c2y, p2.x(), p2.y())
