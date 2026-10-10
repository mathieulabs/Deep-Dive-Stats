# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Card surface shared by chart cards and stat cards.

The glass slider k (0 to 1) goes from a faint light veil to an opaque card in
dark mode:
- up to k0 the veil is unchanged (veil_alpha(k));
- above it the veil becomes the theme card color and reaches full opacity at
  k = 1, hiding whatever is behind (e.g. a wallpaper behind pinned widgets).
"""

from aqt.qt import QColor


def _mix(a, b, t):
    return QColor(
        int(round(a.red() + (b.red() - a.red()) * t)),
        int(round(a.green() + (b.green() - a.green()) * t)),
        int(round(a.blue() + (b.blue() - a.blue()) * t)),
    )


def opaque_card_color(theme_bg):
    """The solid card color reached at 100%: the theme bg, one step lighter."""
    bg = QColor(theme_bg) if theme_bg is not None else QColor("#2f2f31")
    if not bg.isValid():
        bg = QColor("#2f2f31")
    return _mix(bg, QColor("#ffffff"), 0.08)


def dark_surface_rgba(k, theme_bg, veil_alpha, k0=0.2):
    """rgba() string for a dark-mode card at glass intensity k (0-1)."""
    k = max(0.0, min(1.0, float(k)))
    white = QColor("#ffffff")
    if k <= k0:
        return f"rgba(255, 255, 255, {veil_alpha(k):.3f})"
    t = (k - k0) / (1.0 - k0)
    a0 = veil_alpha(k0)
    alpha = a0 + (1.0 - a0) * (t ** 1.4)
    # Reach the card color quickly: a white veil at mid opacity looks milky.
    col = _mix(white, opaque_card_color(theme_bg), min(1.0, t * 8.0))
    return f"rgba({col.red()}, {col.green()}, {col.blue()}, {alpha:.3f})"
