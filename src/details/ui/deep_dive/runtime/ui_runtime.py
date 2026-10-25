# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QEasingCurve, QGraphicsOpacityEffect, QPropertyAnimation, Qt

from ....animations.motion import animations_enabled
from ....logic.logger import log_swallowed


def _fade_in(dialog):
    """Fade the Deep Dive area in. The opacity effect only lives for the fade: left on, it
    renders the whole area (charts, table drawer) off screen on every repaint."""
    box = dialog.expanded_container
    if not animations_enabled("details"):
        box.setGraphicsEffect(None)
        return
    effect = QGraphicsOpacityEffect(box)
    effect.setOpacity(0.0)
    box.setGraphicsEffect(effect)  # also deletes an effect left by an earlier fade
    anim = QPropertyAnimation(effect, b"opacity", effect)
    anim.setDuration(400)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutQuad)

    def _done():
        try:
            if box.graphicsEffect() is effect:
                box.setGraphicsEffect(None)
        except RuntimeError:
            pass

    anim.finished.connect(_done)
    anim.start()


def show_and_animate(manager):
    if hasattr(manager.dialog, "layout_toggle_container"):
        manager.dialog.layout_toggle_container.setVisible(True)
    if hasattr(manager.dialog, "deck_select_btn"):
        manager.dialog.deck_select_btn.setVisible(True)
        manager.dialog.span_select_btn.setVisible(True)

    # Always keep container visible so handle stays accessible.
    was_hidden = not manager.dialog.expanded_container.isVisible()
    if was_hidden:
        manager.dialog.expanded_container.setVisible(True)
        _fade_in(manager.dialog)

    # apply_layout_state in dialog handles 0-size if layout_state == 0.
    manager.dialog.apply_layout_state(animated=False)

    if hasattr(manager.dialog, "expanded_title"):
        manager.dialog.expanded_title.setCursor(Qt.CursorShape.ArrowCursor)
        manager.dialog.expanded_title.mousePressEvent = None

    manager.dialog.expanded_container.setVisible(True)
    try:
        from ...details_dialog.table_drawer import sync

        sync(manager.dialog)
    except Exception:
        log_swallowed()
