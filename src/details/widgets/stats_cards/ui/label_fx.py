# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QColor, QGraphicsDropShadowEffect


def apply_text_shadow(owner, label, opacity):
    """Apply cached drop-shadow effect to a text label."""
    last_opacity = getattr(label, "_last_shadow_opacity", -1)
    if abs(last_opacity - opacity) < 0.01:
        return
    label._last_shadow_opacity = opacity

    if opacity <= 0.01:
        label.setGraphicsEffect(None)
        return

    shadow = QGraphicsDropShadowEffect(owner)
    shadow.setBlurRadius(4)
    shadow.setOffset(0, 1)
    shadow.setColor(QColor(0, 0, 0, int(255 * opacity)))
    label.setGraphicsEffect(shadow)


