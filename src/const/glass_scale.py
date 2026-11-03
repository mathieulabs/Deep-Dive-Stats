# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Scale of the box background slider (pinned charts, text widget, heatmap, Deep Dive
cards). Pure math, shared by the card styling and the config migration."""

# Box background slider (charts, text widget, heatmap): the value is how much of the box
# shows, so 0 is see-through, 50 half covered, 100 opaque. The look itself is the curve
# below (veil, then card color); the slider just walks along it evenly.
_VEIL_K0 = 0.2


def _veil_alpha(k):
    return 0.02 + k * 0.12


def _box_alpha(k):
    """Opacity of the dark-mode box at curve position k (0 to 1)."""
    k = max(0.0, min(1.0, float(k)))
    if k <= _VEIL_K0:
        return _veil_alpha(k)
    a0 = _veil_alpha(_VEIL_K0)
    return a0 + (1.0 - a0) * (((k - _VEIL_K0) / (1.0 - _VEIL_K0)) ** 1.4)


def box_glass_k(value):
    """Slider value (0 to 100) to the position k on the box curve."""
    a = max(0.0, min(1.0, float(value) / 100.0))
    a0 = _veil_alpha(_VEIL_K0)
    if a <= a0:
        return max(0.0, (a - _veil_alpha(0.0)) / 0.12)
    return _VEIL_K0 + (1.0 - _VEIL_K0) * (((a - a0) / (1.0 - a0)) ** (1.0 / 1.4))


def box_value_from_old(old_value):
    """An intensity saved with the old slider (where the value was k itself) on the new
    slider, so the box looks the same."""
    try:
        return int(round(_box_alpha(float(old_value) / 100.0) * 100.0))
    except (TypeError, ValueError):
        return old_value
