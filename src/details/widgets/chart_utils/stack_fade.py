# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Page switch of a QStackedWidget (bars <-> one dot per review).

The old page fades out first, then the new one fades in. Both are never visible at the
same time, so axes and labels of the two views do not overlap during the switch.
"""
from aqt.qt import QEasingCurve, QGraphicsOpacityEffect, QLabel, Qt, QVariantAnimation

from ...animations.motion import animations_enabled
from ...logic.logger import log_swallowed

FADE_MS = 380
_SPLIT = 0.42  # share of the time spent fading the old page out
_EASE = QEasingCurve(QEasingCurve.Type.InOutSine)


def _clear_new_effect(page, effect):
    try:
        if page is not None and effect is not None and page.graphicsEffect() is effect:
            page.setGraphicsEffect(None)
    except RuntimeError:
        pass


def _drop_overlay(stack):
    state = getattr(stack, "_fade_state", None)
    stack._fade_state = None
    if not state:
        return
    try:
        state["anim"].stop()
    except RuntimeError:
        pass
    _clear_new_effect(state.get("page"), state.get("effect"))
    try:
        state["overlay"].hide()
        state["overlay"].deleteLater()
    except RuntimeError:
        pass


def set_stack_index_animated(stack, index, scope="all"):
    """Like stack.setCurrentIndex(index), with a fade out / fade in."""
    try:
        if stack.currentIndex() == index:
            return
        _drop_overlay(stack)
        old = stack.currentWidget()
        if old is None or not stack.isVisible() or stack.width() < 20 or not animations_enabled(scope):
            stack.setCurrentIndex(index)
            return
        pixmap = old.grab()
        stack.setCurrentIndex(index)
        page = stack.currentWidget()

        overlay = QLabel(stack)
        overlay.setPixmap(pixmap)
        overlay.setGeometry(stack.rect())
        overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        old_effect = QGraphicsOpacityEffect(overlay)
        overlay.setGraphicsEffect(old_effect)

        new_effect = None
        if page is not None and page.graphicsEffect() is None:
            new_effect = QGraphicsOpacityEffect(page)
            new_effect.setOpacity(0.0)
            page.setGraphicsEffect(new_effect)

        state = {"overlay": overlay, "page": page, "effect": new_effect, "intro": False}

        def _step(value, st=state, oe=old_effect):
            v = float(value)
            try:
                if v < _SPLIT:
                    oe.setOpacity(1.0 - _EASE.valueForProgress(v / _SPLIT))
                    if st["effect"] is not None:
                        st["effect"].setOpacity(0.0)
                    return
                oe.setOpacity(0.0)
                if not st["intro"]:
                    st["intro"] = True
                    # The new view starts its own reveal once it can be seen.
                    start = getattr(st["page"], "_start_intro", None)
                    if callable(start):
                        start()
                if st["effect"] is not None:
                    st["effect"].setOpacity(_EASE.valueForProgress((v - _SPLIT) / (1.0 - _SPLIT)))
            except RuntimeError:
                pass

        anim = QVariantAnimation(overlay)
        anim.setDuration(FADE_MS)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.valueChanged.connect(_step)
        anim.finished.connect(lambda s=stack, st=state: _finish(s, st))
        state["anim"] = anim
        stack._fade_state = state
        overlay.show()
        overlay.raise_()
        _step(0.0)
        anim.start()
    except Exception:
        log_swallowed()
        try:
            stack.setCurrentIndex(index)
        except Exception:
            pass


def _finish(stack, state):
    try:
        if getattr(stack, "_fade_state", None) is state:
            stack._fade_state = None
    except RuntimeError:
        pass
    _clear_new_effect(state.get("page"), state.get("effect"))
    try:
        state["overlay"].hide()
        state["overlay"].deleteLater()
    except RuntimeError:
        pass
