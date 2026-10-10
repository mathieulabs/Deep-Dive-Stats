# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Row packing shared by the stats-card and pinned masonry layouts."""


def project_row_positions(base_xs, desired_xs, widths, row_min, row_spacing, row_max=None, weights=None):
    n = len(base_xs)
    if n == 0:
        return []
    if not weights or len(weights) != n:
        weights = [1.0] * n

    # Turn the overlap constraints into monotonic ones:
    # p_i >= p_{i-1} + w_{i-1} + spacing  <=>  q_i >= q_{i-1}, with q_i = p_i - prefix_i.
    prefix = [0] * n
    for i in range(1, n):
        prefix[i] = prefix[i - 1] + int(widths[i - 1]) + int(row_spacing)
    r = [float(desired_xs[i] - prefix[i]) for i in range(n)]

    # Pool Adjacent Violators (isotonic regression, equal weights)
    blocks = []  # [start, end, weighted_sum, weight_sum, mean]
    for i, val in enumerate(r):
        w = float(weights[i])
        if w <= 0:
            w = 1.0
        blocks.append([i, i, val * w, w, val])
        while len(blocks) >= 2 and blocks[-2][4] > blocks[-1][4]:
            b2 = blocks.pop()
            b1 = blocks.pop()
            s = b1[2] + b2[2]
            c = b1[3] + b2[3]
            blocks.append([b1[0], b2[1], s, c, s / c])

    q = [0.0] * n
    for b in blocks:
        v = max(float(row_min), float(b[4]))
        for i in range(b[0], b[1] + 1):
            q[i] = v

    xs = [int(round(q[i] + prefix[i])) for i in range(n)]
    xs[0] = max(int(xs[0]), int(row_min))
    for i in range(1, n):
        min_x = int(xs[i - 1] + widths[i - 1] + row_spacing)
        if xs[i] < min_x:
            xs[i] = min_x

    if row_max is not None and n > 0:
        max_last_x = int(row_max - widths[-1])
        if xs[-1] > max_last_x:
            xs[-1] = max_last_x
        for i in range(n - 2, -1, -1):
            max_x = int(xs[i + 1] - widths[i] - row_spacing)
            if xs[i] > max_x:
                xs[i] = max_x
        if xs[0] < int(row_min):
            xs[0] = int(row_min)
        for i in range(1, n):
            min_x = int(xs[i - 1] + widths[i - 1] + row_spacing)
            if xs[i] < min_x:
                xs[i] = min_x
    return xs
