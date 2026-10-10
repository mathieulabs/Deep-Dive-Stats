# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import (
    QPainter, QPen, QColor, QLinearGradient, QBrush, Qt, QRectF
)
from ..widgets.chart_utils import is_night_mode
from .motion import animations_enabled
from .anim_driver import _hover_driver

class StatCardEffect:
    _OPACITY_STEP = 0.08

    def __init__(self, parent_widget):
        self._parent = parent_widget
        self._opacity = 0.0
        self._locked = False
        self._is_hovered = False
        self._state = 0 # 0: IDLE, 1: FADE_IN, 2: ACTIVE, 3: FADE_OUT
        self._grad_cache = None
        self._last_rect = None
        self._last_color = None

    def _on_global_tick(self):
        """Called by _GlobalHoverDriver. Returns True if still needs ticks."""
        if self._state == 1:
            self._opacity += self._OPACITY_STEP
            if self._opacity >= 1.0:
                self._opacity = 1.0
                self._state = 2
                self._parent.update()
                return False  # done, unregister
        elif self._state == 3:
            self._opacity -= self._OPACITY_STEP
            if self._opacity <= 0.0:
                self._opacity = 0.0
                self._state = 0
                if self._parent.parentWidget():
                    p = self._parent.parentWidget()
                    margin = 4
                    geom = self._parent.geometry().adjusted(-margin, -margin, margin, margin)
                    p.update(geom)
                self._parent.update()
                return False  # done, unregister
            if self._parent.parentWidget():
                p = self._parent.parentWidget()
                margin = 4
                geom = self._parent.geometry().adjusted(-margin, -margin, margin, margin)
                p.update(geom)
        else:
            return False  # idle or active: should not be registered

        self._parent.update()
        return True  # still transitioning

    def _register(self):
        _hover_driver.register(self)

    def _unregister(self):
        _hover_driver.unregister(self)

    def start(self):
        self._is_hovered = True
        scope = "pinned" if bool(getattr(self._parent, "is_pinned", False)) else "details"
        if not animations_enabled(scope):
            if self._locked or self._is_hovered:
                self._opacity = 1.0
                self._state = 2
            else:
                self._opacity = 0.0
                self._state = 0
            self._unregister()
            self._parent.update()
            return
        if self._locked:
            return
        self._state = 1
        self._register()

    def stop(self):
        self._is_hovered = False
        scope = "pinned" if bool(getattr(self._parent, "is_pinned", False)) else "details"
        if not animations_enabled(scope):
            if self._locked:
                self._opacity = 1.0
                self._state = 2
            else:
                self._opacity = 0.0
                self._state = 0
            self._unregister()
            self._parent.update()
            return
        if self._locked:
            return
        self._state = 3
        self._register()

    def toggle_lock(self):
        scope = "pinned" if bool(getattr(self._parent, "is_pinned", False)) else "details"
        if not animations_enabled(scope):
            self._locked = not self._locked
            if self._locked or self._is_hovered:
                self._opacity = 1.0
                self._state = 2
            else:
                self._opacity = 0.0
                self._state = 0
            self._unregister()
            self._parent.update()
            return
        self._locked = not self._locked
        if self._locked:
            if self._opacity < 1.0:
                self._state = 1
                self._register()
            else:
                self._state = 2
                self._unregister()
        else:
            self._state = 3
            self._register()

    def paint(self, painter: QPainter, widget_rect, base_color_hex: str, max_opacity: float = 1.0):
        """
        Draws a static adaptive glow border around the widget.
        """
        if self._state == 0 and self._opacity <= 0.001:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipRect(widget_rect)

        actual_opacity = self._opacity * max_opacity

        radius = 12
        margin = 1.0
        draw_rect = QRectF(widget_rect).adjusted(margin, margin, -margin, -margin)

        base = QColor(base_color_hex)
        base.setAlphaF(actual_opacity)
        # Use addon/theme-aware dark detection first (more reliable than raw palette).
        is_light_bg = not is_night_mode(self._parent)

        lighter = base.lighter(150)
        lighter.setAlphaF(actual_opacity)

        if self._last_rect != draw_rect or self._last_color != base_color_hex:
            self._last_rect = draw_rect
            self._last_color = base_color_hex

            grad = QLinearGradient(draw_rect.topLeft(), draw_rect.bottomRight())
            # We store the gradient object, but we'll still update colors if opacity changes
            self._grad_cache = grad

        if is_light_bg:
            # Light mode: slight brighten with same hue (no white/gray highlight).
            edge = QColor(base_color_hex).lighter(112)
            edge.setAlphaF(0.55 * actual_opacity)
            mid = QColor(base_color_hex).lighter(106)
            mid.setAlphaF(0.78 * actual_opacity)
            self._grad_cache.setColorAt(0.0, edge)
            self._grad_cache.setColorAt(0.3, mid)
            self._grad_cache.setColorAt(1.0, base)
        else:
            white_core = QColor("#ffffff")
            white_core.setAlphaF(0.85 * actual_opacity)
            self._grad_cache.setColorAt(0.0, white_core)
            self._grad_cache.setColorAt(0.3, lighter)
            self._grad_cache.setColorAt(1.0, base)

        pen_width = 1.4
        pen = QPen(QBrush(self._grad_cache), pen_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Draw with adjusted radius to match the inset rectangle geometry
        adj_radius = max(0, radius - margin)
        painter.drawRoundedRect(draw_rect, adj_radius, adj_radius)

        painter.restore()
