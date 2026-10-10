# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from aqt.qt import QPropertyAnimation, QEasingCurve
from .motion import animations_enabled


def animate_widget_geometry(widget, start_rect, end_rect, animations_dict, duration=300):
    """Animate a widget from start_rect to end_rect.

    The running animation is stored in animations_dict so it is not garbage
    collected and a previous one on the same widget can be stopped first.
    """
    if not animations_enabled("pinned"):
        widget.setGeometry(end_rect)
        return

    if widget in animations_dict:
        animations_dict[widget].stop()

    anim = QPropertyAnimation(widget, b"geometry")
    anim.setDuration(duration)
    anim.setStartValue(start_rect)
    anim.setEndValue(end_rect)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    def _forget(_w=widget, _a=anim):
        if animations_dict.get(_w) is _a:
            animations_dict.pop(_w, None)

    anim.finished.connect(_forget)
    anim.start()
    animations_dict[widget] = anim
