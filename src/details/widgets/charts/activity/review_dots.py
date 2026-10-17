# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""One dot per review, shown when the Activity chart is zoomed to a few hours."""
import math
from datetime import datetime

from aqt.qt import QColor, QEasingCurve, QFont, QPainter, QPen, QPointF, QRectF, QSizePolicy, Qt, QVariantAnimation, QWidget

from ....animations.motion import animations_enabled

from ...chart_utils.theme import get_theme_colors
from ...chart_utils.tooltip import TooltipWindow, show_tooltip_near
from ....logic.logger import log_swallowed

_KIND_NAMES = ("Learning", "Young", "Mature", "Relearning", "Filtered")
_EASE_NAMES = {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}
_MARGIN_L, _MARGIN_R, _MARGIN_T, _MARGIN_B = 45, 20, 10, 30


# One dot per review only once the 10-minute view is zoomed down to 3 hours or less;
# above that the 10-minute bars stay.
DOTS_MAX_SPAN_MS = 3 * 3600 * 1000


class ReviewDotsChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._events = []
        self._events_shown = False
        self._t0 = 0
        self._t1 = 1
        self._v0 = 0
        self._v1 = 1
        self._mode = "reviews"
        self._breakdown = False
        self._bar_color = QColor("#4c8bf5")
        self._kind_colors = [QColor("#888")] * 5
        self._points = []
        self._intro = 1.0
        self._intro_anim = None
        self._mode_anim = None
        self._mode_from = None
        self._mode_e = 1.0
        self.wheel_target = None
        self.zoom_out_handler = None
        self._view_target = None
        self.tooltip_window = TooltipWindow(self)
        self.setMouseTracking(True)
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def showEvent(self, event):
        super().showEvent(event)
        self._start_intro()

    def _start_intro(self):
        """Dots pop in from left to right when the chart appears."""
        if self._intro_anim is not None:
            self._intro_anim.stop()
        if not animations_enabled("all") or not self._events:
            self._intro = 1.0
            return
        if self._intro_anim is None:
            anim = QVariantAnimation(self)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.Linear)
            anim.valueChanged.connect(self._on_intro)
            anim.finished.connect(self._on_intro_done)
            self._intro_anim = anim
        # Longer for more dots, but always short.
        self._intro_anim.setDuration(int(min(700, 380 + len(self._events) * 0.5)))
        self._intro = 0.0
        self._intro_anim.start()

    def finish_intro(self):
        if self._intro_anim is not None:
            self._intro_anim.stop()
        self._intro = 1.0

    def _on_intro(self, value):
        self._intro = float(value)
        self.update()

    def _on_intro_done(self):
        self._intro = 1.0
        self.update()

    def zoom_window_seconds(self):
        """Time window shown, in seconds (for the zoom animation)."""
        return (self._v0 / 1000.0, self._v1 / 1000.0) if self._v1 > self._v0 else None

    def _get_margins(self):
        return _MARGIN_L, _MARGIN_R

    def set_style(self, bar_color, kind_colors):
        self._bar_color = QColor(bar_color)
        self._kind_colors = [QColor(c) for c in kind_colors]
        self.update()

    def set_mode(self, mode, breakdown):
        """Reviews <-> Time. The dots sit by rank in Reviews and by duration in Time, so
        on a switch they glide to their new height instead of jumping."""
        mode = "time" if mode == "time" else "reviews"
        self._breakdown = bool(breakdown)
        if mode == self._mode:
            self.update()
            return
        running = self._mode_anim is not None and self._mode_anim.state() == QVariantAnimation.State.Running
        if running and mode == self._mode_from:
            # Switched back mid-glide: reverse from where the dots are now.
            e = self._mode_e
            self._mode_from = self._mode
            self._mode = mode
            self._run_mode_morph(1.0 - e)
            return
        can_glide = bool(self._events) and self._events_shown and self.isVisible() and animations_enabled("all")
        previous = self._mode
        self._mode = mode
        if can_glide:
            self._mode_from = previous
            self._run_mode_morph(0.0)
        else:
            self._stop_mode_morph()
            self.update()

    def _run_mode_morph(self, start):
        anim = self._mode_anim
        if anim is None:
            anim = QVariantAnimation(self)
            anim.setEndValue(1.0)
            anim.setDuration(320)
            anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
            anim.valueChanged.connect(self._on_mode_morph)
            anim.finished.connect(self._on_mode_morph_done)
            self._mode_anim = anim
        anim.stop()
        anim.setStartValue(float(start))
        self._mode_e = float(start)
        anim.start()
        self.update()

    def _stop_mode_morph(self):
        if self._mode_anim is not None:
            self._mode_anim.stop()
        self._mode_from = None
        self._mode_e = 1.0

    def _on_mode_morph(self, value):
        self._mode_e = float(value)
        self.update()

    def _on_mode_morph_done(self):
        self._mode_from = None
        self._mode_e = 1.0
        self.update()

    def set_events(self, events, t0_ms, t1_ms):
        self._events = list(events or [])
        t0, t1 = int(t0_ms), max(int(t1_ms), int(t0_ms) + 1)
        if (t0, t1) != (self._t0, self._t1):
            widened = (
                bool(self._events_shown) and self.isVisible() and animations_enabled("all")
                and t0 <= self._v0 and t1 >= self._v1 and t1 - t0 > self._v1 - self._v0
            )
            if widened:
                # Zooming out: keep what is on screen and glide to the wider window.
                self._t0, self._t1 = t0, t1
                self._animate_view(t0, t1 - t0)
                self._events_shown = bool(events)
                self.update()
                return
            self._stop_view_anim()
            self._v0, self._v1 = t0, t1
        self._t0, self._t1 = t0, t1
        self._events_shown = True
        self.update()

    def _y_values_for(self, mode):
        if mode == "time":
            return [e[1] / 1000.0 for e in self._events]
        return list(range(1, len(self._events) + 1))

    def _y_values(self):
        return self._y_values_for(self._mode)

    def _dot_color(self, event):
        c = self._kind_colors[event[3]] if self._breakdown else self._bar_color
        c = QColor(c)
        c.setAlpha(200)
        return c

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        colors = get_theme_colors(self)
        text = QColor(colors.get("text", QColor("#888")))
        grid = QColor(colors.get("grid", QColor("#888")))
        w, h = self.width(), self.height()
        px, py = _MARGIN_L, _MARGIN_T
        pw, ph = w - _MARGIN_L - _MARGIN_R, h - _MARGIN_T - _MARGIN_B
        if pw <= 10 or ph <= 10:
            return
        font = QFont(self.font())
        font.setPointSizeF(max(7.0, font.pointSizeF() - 1))
        p.setFont(font)

        ys = self._y_values()
        ymax = max(ys) if ys else 1
        ymax = max(ymax, 1)
        morph = self._mode_from if (self._mode_from is not None and self._mode_from != self._mode) else None
        me = max(0.0, min(1.0, self._mode_e)) if morph else 1.0
        if morph:
            ys_from = self._y_values_for(morph)
            ymax_from = max(max(ys_from) if ys_from else 1, 1)
        grid_pen = QPen(grid)
        grid_pen.setWidthF(0.5)
        # Axes fade in at the start of the intro (the bars they replace fade out meanwhile).
        axes_opacity = min(1.0, self._intro * 2.5)
        p.setOpacity(axes_opacity)
        for i in range(5):
            frac = i / 4
            y = py + ph - frac * ph
            p.setPen(grid_pen)
            p.drawLine(int(px), int(y), int(px + pw), int(y))
            p.setPen(text)
            labels = [(self._mode, ymax, me)]
            if morph:
                labels.append((morph, ymax_from, 1.0 - me))
            for lab_mode, lab_max, lab_alpha in labels:
                val = lab_max * frac
                label = f"{val:.0f}" if (lab_mode == "reviews" or lab_max >= 10) else f"{val:.1f}"
                if lab_mode == "time":
                    label += "s"
                p.setOpacity(axes_opacity * lab_alpha)
                p.drawText(0, int(y) - 8, px - 6, 16, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, label)
            p.setOpacity(axes_opacity)

        v0, v1 = self._v0, self._v1
        span = v1 - v0
        step_ms = _nice_step_seconds(span / 1000.0, max(2, pw // 70)) * 1000
        t = (v0 // step_ms + 1) * step_ms if v0 % step_ms else v0
        p.setPen(text)
        while t <= v1:
            x = px + (t - v0) / span * pw
            p.setPen(grid_pen)
            p.drawLine(int(x), int(py), int(x), int(py + ph))
            p.setPen(text)
            fmt = "%H:%M:%S" if step_ms < 60000 else "%H:%M"
            label = datetime.fromtimestamp(t / 1000).strftime(fmt)
            p.drawText(int(x) - 30, int(py + ph + 4), 60, 18, Qt.AlignmentFlag.AlignCenter, label)
            t += step_ms

        p.setOpacity(1.0)
        self._points = []
        n = len(self._events)
        radius = 3.5 if n <= 300 else 2.5 if n <= 700 else 2.0
        p.setPen(Qt.PenStyle.NoPen)
        intro = self._intro
        for k, (ev, yv) in enumerate(zip(self._events, ys)):
            x = px + (ev[0] - v0) / span * pw
            if x < px - 1 or x > px + pw + 1:
                continue
            yn = yv / ymax
            if morph and k < len(ys_from):
                yn_from = ys_from[k] / ymax_from
                yn = yn_from + (yn - yn_from) * me
            y = py + ph - yn * ph
            color = self._dot_color(ev)
            r = radius
            if intro < 1.0:
                # Each dot starts a little later the further right it is.
                local = max(0.0, min(1.0, (intro * 1.6 - ((x - px) / pw) * 0.6)))
                local = 1.0 - (1.0 - local) ** 3
                r = radius * (0.3 + 0.7 * local)
                color.setAlpha(int(color.alpha() * local))
            p.setBrush(color)
            p.drawEllipse(QPointF(x, y), r, r)
            self._points.append((x, y, ev))
        if not self._events:
            p.setPen(text)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No reviews in this window")
        press = getattr(self, "_press_pos", None)
        drag_x = getattr(self, "_drag_x", None)
        if press is not None and drag_x is not None:
            x1 = max(px, min(press.x(), drag_x))
            x2 = min(px + pw, max(press.x(), drag_x))
            if x2 > x1:
                acc = QColor(colors.get("accent", QColor(59, 130, 246)))
                fill = QColor(acc)
                fill.setAlpha(20)
                rect = QRectF(x1, py, x2 - x1, ph)
                p.fillRect(rect, fill)
                acc.setAlpha(200)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(acc, 1.5))
                p.drawRect(rect)
        p.end()

    def _nearest(self, pos):
        best, best_d = None, 64.0
        for x, y, ev in self._points:
            d = (x - pos.x()) ** 2 + (y - pos.y()) ** 2
            if d < best_d:
                best, best_d = ev, d
        return best

    def mousePressEvent(self, event):
        self._press_pos = event.position()
        self._drag_x = None
        super().mousePressEvent(event)

    def _plot_span_x(self):
        return _MARGIN_L, max(1, self.width() - _MARGIN_L - _MARGIN_R)

    def _x_to_time(self, x):
        px, pw = self._plot_span_x()
        frac = min(1.0, max(0.0, (x - px) / pw))
        return self._v0 + frac * (self._v1 - self._v0)

    def mouseReleaseEvent(self, event):
        p = getattr(self, "_press_pos", None)
        self._press_pos = None
        drag_x = getattr(self, "_drag_x", None)
        self._drag_x = None
        if p is not None and event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            if drag_x is not None and abs(pos.x() - p.x()) > 5:
                # Zone selection: zoom the view on it (at least one minute).
                a, b = sorted((self._x_to_time(p.x()), self._x_to_time(pos.x())))
                if b - a < 60000:
                    mid = (a + b) / 2.0
                    a, b = mid - 30000, mid + 30000
                self._animate_view(a, b - a)
                self.update()
            elif abs(pos.x() - p.x()) + abs(pos.y() - p.y()) <= 5:
                ev = self._nearest(pos)
                if ev is not None and len(ev) > 4:
                    try:
                        from ....logic.interactions import browser_search
                        browser_search.open_card(ev[4])
                    except Exception:
                        log_swallowed()
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position()
        press = getattr(self, "_press_pos", None)
        if press is not None and (event.buttons() & Qt.MouseButton.LeftButton) and abs(pos.x() - press.x()) > 5:
            self._drag_x = pos.x()
            self.tooltip_window.hide()
            self.update()
            return
        best = self._nearest(pos)
        self.setCursor(Qt.CursorShape.PointingHandCursor if best is not None else Qt.CursorShape.ArrowCursor)
        if best is None:
            self.tooltip_window.hide()
            return
        dt = datetime.fromtimestamp(best[0] / 1000)
        kind_line = {"text": _KIND_NAMES[best[3]], "value": f"{best[1] / 1000:.1f}s"}
        if self._breakdown:
            kind_line["color"] = self._kind_colors[best[3]]
        lines = [
            {"text": dt.strftime("%b %d, %H:%M:%S"), "header": True},
            kind_line,
            {"text": "Answer", "value": _EASE_NAMES.get(best[2], "?")},
        ]
        show_tooltip_near(self, self.tooltip_window, event.pos(), lines=lines, show_only_if_hidden=True)

    def leaveEvent(self, event):
        self.tooltip_window.hide()
        super().leaveEvent(event)

    def wheelEvent(self, event):
        mods = event.modifiers()
        delta = event.angleDelta().y() or event.angleDelta().x()
        full = self._t1 - self._t0
        span = self._v1 - self._v0
        pw = max(1, self.width() - _MARGIN_L - _MARGIN_R)
        if mods & Qt.KeyboardModifier.ControlModifier and delta:
            zoom_in = delta > 0
            target_span = self._view_target[1] if (self._view_target and self._view_anim_running()) else span
            if not zoom_in and max(span, target_span) >= full * 0.999:
                frac = min(1.0, max(0.0, (event.position().x() - _MARGIN_L) / pw))
                handler = self.zoom_out_handler
                try:
                    if handler is not None and handler(frac):
                        return
                except Exception:
                    log_swallowed()
                self._forward_wheel(event)
                return
            frac = min(1.0, max(0.0, (event.position().x() - _MARGIN_L) / pw))
            anchor = self._v0 + frac * span
            new_span = span * (0.8 if zoom_in else 1.25)
            new_span = min(full, max(60000, new_span))
            self._set_view(anchor - frac * new_span, new_span)
            return
        if mods & Qt.KeyboardModifier.ShiftModifier and delta:
            self._set_view(self._v0 - span * 0.1 * (1 if delta > 0 else -1), span)
            return
        self._forward_wheel(event)

    def _set_view(self, v0, span):
        self._stop_view_anim()
        self._apply_view(v0, span)

    def _apply_view(self, v0, span):
        span = min(max(span, 1), self._t1 - self._t0)
        v0 = min(max(v0, self._t0), self._t1 - span)
        self._v0, self._v1 = int(v0), int(v0 + span)
        self.update()

    def _view_anim_running(self):
        anim = getattr(self, "_view_anim", None)
        return anim is not None and anim.state() == QVariantAnimation.State.Running

    def _stop_view_anim(self):
        anim = getattr(self, "_view_anim", None)
        if anim is not None:
            anim.stop()

    def _animate_view(self, v0, span):
        """Move the view to (v0, v0 + span) with a short zoom animation."""
        self._stop_view_anim()
        span = min(max(span, 1), self._t1 - self._t0)
        v0 = min(max(v0, self._t0), self._t1 - span)
        if not animations_enabled("all") or not self.isVisible():
            self._apply_view(v0, span)
            return
        a0, aw = float(self._v0), float(max(1, self._v1 - self._v0))
        b0, bw = float(v0), float(span)
        self._view_target = (b0, bw)
        anim = getattr(self, "_view_anim", None)
        if anim is None:
            anim = QVariantAnimation(self)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setDuration(320)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._view_anim = anim
        try:
            anim.valueChanged.disconnect()
        except (TypeError, RuntimeError):
            pass

        def step(e, a0=a0, aw=aw, b0=b0, bw=bw):
            e = float(e)
            w = math.exp(math.log(aw) + (math.log(bw) - math.log(aw)) * e)
            if abs(bw - aw) < 1e-6 * max(aw, bw):
                start = a0 + (b0 - a0) * e
            else:
                p = (a0 * bw - b0 * aw) / (bw - aw)
                start = p - (p - a0) * w / aw
            self._apply_view(start, w)

        anim.valueChanged.connect(step)
        anim.start()

    def _forward_wheel(self, event):
        target = self.wheel_target
        if target is not None:
            try:
                target.wheelEvent(event)
                return
            except RuntimeError:
                pass
        super().wheelEvent(event)


def _nice_step_seconds(span_s, max_ticks):
    for step in (5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200, 14400):
        if span_s / step <= max_ticks:
            return step
    return 14400
