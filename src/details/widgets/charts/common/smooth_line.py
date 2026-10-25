# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Slightly rounded polyline for cumulative ("Total") lines."""


def add_smooth_line(path, points, smoothing=1.0):
    """Append segments to path (already at points[0]) with softened corners.

    Monotone cubic (Fritsch-Butland tangents, scaled by smoothing, 1.0 = full): the
    curve never dips or overshoots between two points, flat stretches stay flat, and
    each point has one tangent shared by the segments on both sides, so there is no
    small corner where they meet.
    """
    n = len(points)
    if n < 3:
        for p in points[1:]:
            path.lineTo(p)
        return
    # x and y read once per point (a QPointF call costs more than the arithmetic around it)
    xs = [p.x() for p in points]
    ys = [p.y() for p in points]
    last = n - 1
    hs = [xs[i + 1] - xs[i] for i in range(last)]
    if any(h <= 0 for h in hs):
        # Not left to right (should not happen): plain segments.
        for p in points[1:]:
            path.lineTo(p)
        return
    ds = [(ys[i + 1] - ys[i]) / hs[i] for i in range(last)]
    ms = [0.0] * n
    ms[0], ms[last] = ds[0], ds[last - 1]
    for i in range(1, last):
        d0, d1 = ds[i - 1], ds[i]
        if d0 * d1 > 0:
            h0, h1 = hs[i - 1], hs[i]
            ms[i] = 3.0 * (h0 + h1) / ((2.0 * h1 + h0) / d0 + (h1 + 2.0 * h0) / d1)
    # An end next to a flat or turning segment keeps a tangent that cannot overshoot.
    for i, j in ((0, 0), (last, last - 1)):
        if ds[j] == 0 or ms[i] * ds[j] < 0:
            ms[i] = 0.0
    cubic = path.cubicTo
    for i in range(last):
        h3 = hs[i] / 3.0
        cubic(
            xs[i] + h3, ys[i] + ms[i] * smoothing * h3,
            xs[i + 1] - h3, ys[i + 1] - ms[i + 1] * smoothing * h3,
            xs[i + 1], ys[i + 1],
        )
