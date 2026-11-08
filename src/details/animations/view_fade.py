# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The "Fade" transition style: a chart takes its new data at once (its own animations end
on their last frame) and its old picture fades into the new one.

snap_animations() is shared with the Deep Dive glide (ui.deep_dive.layout_parts.grid_fade);
capture() / play() fade single widgets (the pinned widgets, updated one by one as their data
comes in)."""

from aqt.qt import QEasingCurve, QEvent, QGraphicsOpacityEffect, QPainter, QPixmap, QVariantAnimation, QWidget, Qt

from ..logic.logger import log_swallowed

DURATION_MS = 280

# Charts with their own transitions besides the mixin's (the Heatmap's fade, fold and slide).
_OWN_TRANSITIONS = (
    ("_data_transition_anim", "_data_transition_active", "_on_data_transition_finished"),
    ("_mode_transition_anim", "_mode_transition_active", "_on_mode_transition_finished"),
    ("_nav_transition_anim", "_nav_transition_active", "_on_nav_transition_finished"),
)


def snap_animations(wrappers):
    """Every chart in wrappers on its last frame now (its new data drawn as is)."""
    from .chart_policy import collect_chart_animation_targets
    from ..widgets.chart_utils import zoom_camera

    for wrapper in wrappers:
        try:
            targets = collect_chart_animation_targets(wrapper)
        except RuntimeError:
            continue
        except Exception:
            log_swallowed()
            continue
        for chart in targets:
            try:
                zoom_camera.finish(chart)
                if hasattr(chart, "_finish_without_animation"):
                    chart._finish_without_animation()
                for anim_name, active_name, done_name in _OWN_TRANSITIONS:
                    anim = getattr(chart, anim_name, None)
                    if anim is None or not getattr(chart, active_name, False):
                        continue
                    anim.stop()
                    getattr(chart, done_name)()
                if hasattr(chart, "_initial_animation_done"):
                    chart._initial_animation_done = True
            except RuntimeError:
                pass
            except Exception:
                log_swallowed()


def style_now(scope):
    """The transition style of updates in scope ("pinned" or "details") now, None when
    animations are off there (the charts then show their new data at once anyway)."""
    try:
        from .motion import animations_enabled, transition_style

        return transition_style(scope) if animations_enabled(scope) else None
    except Exception:
        log_swallowed()
        return None


def fade_wanted(scope):
    """Whether updates in scope use the Fade style now."""
    from .motion import TRANSITION_FADE

    return style_now(scope) == TRANSITION_FADE


def snap_wanted(scope):
    """Whether updates in scope show their new data at once (the "No Animation" style)."""
    from .motion import TRANSITION_NONE

    return style_now(scope) == TRANSITION_NONE


def _fadeable(w):
    try:
        return (
            w is not None
            and w.isVisible()
            and w.width() > 2
            and w.height() > 2
            and w.parentWidget() is not None
            and not getattr(w, "_is_loading", False)  # fades in on its own
        )
    except RuntimeError:
        return False


def _picture(w):
    """What w draws, on a transparent picture: its rounded corners and see-through parts
    stay so (grab() filled the whole rect with the window background, a dark rectangle)."""
    from aqt.qt import QPoint, QRegion

    dpr = float(w.devicePixelRatioF() or 1.0)
    pm = QPixmap(max(1, round(w.width() * dpr)), max(1, round(w.height() * dpr)))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    w.render(pm, QPoint(0, 0), QRegion(), QWidget.RenderFlag.DrawChildren)
    return pm


def capture(widgets, scope="pinned"):
    """{widget: its picture now} of the widgets to fade, before they take new data
    ({} when the Fade style is off; {widget: None} with the "No Animation" style: play()
    then only puts their charts on their last frame)."""
    if snap_wanted(scope):
        return {w: None for w in widgets if w is not None}
    if not fade_wanted(scope):
        return {}
    out = {}
    for w in widgets:
        if not _fadeable(w):
            continue
        fading = getattr(w, "_view_fade", None)
        try:
            if fading is not None:
                fading.finish()
            out[w] = _picture(w)
        except RuntimeError:
            pass
        except Exception:
            log_swallowed()
    return out


def play(captured, duration=DURATION_MS):
    """Fade each captured widget from its old picture to what it shows now."""
    if not captured:
        return
    snap_animations(list(captured))
    for w, old in captured.items():
        if old is None:
            continue
        try:
            if not _fadeable(w) or w.graphicsEffect() is not None:
                continue
            new = _picture(w)
            if new.size() != old.size():
                continue  # resized: no matching pictures
            _WidgetFade(w, old, new, duration).start()
        except RuntimeError:
            pass
        except Exception:
            log_swallowed()


class _WidgetFade(QWidget):
    """Drawn over the widget (a sibling: the widget itself is hidden by an opacity effect at
    0, which Qt skips): its old and new pictures mixed premultiplied, so nothing behind shows
    through halfway."""

    def __init__(self, target, old_pm, new_pm, duration):
        super().__init__(target.parentWidget())
        self._target = target
        self._old, self._new = old_pm, new_pm
        self._e = 0.0
        self._done = False
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setGeometry(target.geometry())
        self._ease = QEasingCurve(QEasingCurve.Type.InOutCubic)
        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(int(duration))
        self._anim.valueChanged.connect(self._on_value)
        self._anim.finished.connect(self.finish)

    def start(self):
        eff = QGraphicsOpacityEffect(self._target)
        eff.setOpacity(0.0)
        self._target.setGraphicsEffect(eff)
        self._target._view_fade = self
        self._target.installEventFilter(self)
        self.show()
        self.raise_()
        self._anim.start()

    def _on_value(self, value):
        self._e = self._ease.valueForProgress(max(0.0, min(1.0, float(value))))
        self.update()

    def eventFilter(self, obj, event):
        # The widget moved, changed size or went: the pictures no longer match it.
        if obj is self._target and event.type() in (QEvent.Type.Move, QEvent.Type.Resize, QEvent.Type.Hide):
            self.finish()
        return False

    def paintEvent(self, _event):
        e = self._e
        mix = QPixmap(self._old.size())
        mix.setDevicePixelRatio(self._old.devicePixelRatio())
        mix.fill(Qt.GlobalColor.transparent)
        q = QPainter(mix)
        q.setOpacity(1.0 - e)
        q.drawPixmap(0, 0, self._old)
        part = QPixmap(self._new.size())
        part.setDevicePixelRatio(self._new.devicePixelRatio())
        part.fill(Qt.GlobalColor.transparent)
        r = QPainter(part)
        r.setOpacity(e)
        r.drawPixmap(0, 0, self._new)
        r.end()
        q.setOpacity(1.0)
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        q.drawPixmap(0, 0, part)
        q.end()
        p = QPainter(self)
        p.drawPixmap(0, 0, mix)
        p.end()

    def finish(self):
        if self._done:
            return
        self._done = True
        try:
            self._anim.stop()
        except RuntimeError:
            pass
        target = self._target
        try:
            target.removeEventFilter(self)
            if getattr(target, "_view_fade", None) is self:
                target._view_fade = None
            eff = target.graphicsEffect()
            if isinstance(eff, QGraphicsOpacityEffect):
                target.setGraphicsEffect(None)
        except RuntimeError:
            pass
        try:
            self.hide()
            self.deleteLater()
        except RuntimeError:
            pass
