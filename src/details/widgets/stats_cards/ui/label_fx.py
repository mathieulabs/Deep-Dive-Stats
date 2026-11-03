# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QColor, QGraphicsDropShadowEffect, QTimer

from ....animations.effect_guard import effect_nested


def apply_text_shadow(owner, label, opacity, _tries=0):
    """Apply cached drop-shadow effect to a text label."""
    last_opacity = getattr(label, "_last_shadow_opacity", -1)
    if abs(last_opacity - opacity) < 0.01:
        return

    if opacity <= 0.01:
        label._last_shadow_opacity = opacity
        label.setGraphicsEffect(None)
        return
    if effect_nested(label, check_children=False):
        # Inside a fade (see effect_guard): the shadow comes once it has ended. A card
        # hidden as a ghost gets its style, shadows included, again when it shows.
        if _tries < 4:
            QTimer.singleShot(500, lambda: _retry(owner, label, opacity, _tries + 1))
        return
    label._last_shadow_opacity = opacity

    shadow = QGraphicsDropShadowEffect(owner)
    shadow.setBlurRadius(4)
    shadow.setOffset(0, 1)
    shadow.setColor(QColor(0, 0, 0, int(255 * opacity)))
    label.setGraphicsEffect(shadow)




def _retry(owner, label, opacity, tries):
    try:
        apply_text_shadow(owner, label, opacity, tries)
    except RuntimeError:
        pass  # the label is gone
