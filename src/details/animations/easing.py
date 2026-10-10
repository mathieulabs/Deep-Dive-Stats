# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
def smooth01(x: float) -> float:
    """Smoothstep: maps x in [0, 1] with ease-in/out (S-curve)."""
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - (2.0 * x))


def bezier01(t: float, c1: float, c2: float) -> float:
    """Cubic Bezier opacity shaping on [0, 1] with fixed endpoints (0, 1).

    c1, c2 are the two interior control-point Y values.
    """
    t = max(0.0, min(1.0, t))
    u = 1.0 - t
    return (3.0 * u * u * t * c1) + (3.0 * u * t * t * c2) + (t * t * t)


def early_fade(value: float, cutoff: float) -> float:
    """Make opacity reach 0 before the transition ends.

    value and cutoff are in [0, 1]. Returns 0 at or below cutoff, ramping to 1 at
    value=1.
    """
    if cutoff <= 0.0:
        return max(0.0, min(1.0, value))
    if value <= cutoff:
        return 0.0
    return (value - cutoff) / (1.0 - cutoff)
