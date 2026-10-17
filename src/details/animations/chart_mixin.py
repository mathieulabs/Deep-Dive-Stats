# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QEasingCurve, QAbstractAnimation, QTimer, pyqtProperty
from .motion import animations_enabled
from .anim_driver import _AnimProxy
from .chart_policy import chart_animations_allowed, chart_animation_force_repaint_requested
from ..logic.logger import log_swallowed

class ChartAnimationMixin:
    # Session-level guard: each pinned widget animates only once per Anki launch.
    _pinned_animated_ids = set()
    # Global count of charts currently running a data-update animation.
    _active_data_animation_count = 0

    def init_animation(self, duration=500, easing=QEasingCurve.Type.OutQuart):
        self._is_chart_anim_target = True
        try:
            from ..widgets.chart_utils.browser_click import install_browser_click
            install_browser_click(self)
        except Exception:
            log_swallowed()
        self._progress = 0.0
        self._initial_animation_done = False
        self._is_data_animating = False
        self._force_repaint_current_animation = False
        self._viewport_skip_count = 0
        self._idle_frame_cache = None
        self._capturing_cache = False
        self._is_resizing = False
        self._resize_debounce_timer = None
        dur = duration if animations_enabled(self._animation_scope()) else 1
        self.animation = _AnimProxy(self, duration=dur, easing=easing)
        self.animation.finished.connect(self._on_data_animation_finished)
        # Wrap paintEvent once to serve idle-frame cache without touching each chart.
        if not getattr(self, "_paintEvent_cache_installed", False):
            _orig_pe = self.paintEvent
            def _cached_pe(event, _orig=_orig_pe):
                if self._capturing_cache:
                    _orig(event)
                    return
                cache = self._idle_frame_cache
                # Visual export: always paint for real. The idle frame is a screen-resolution
                # grab and would be blurry when the export draws the chart at 2x.
                try:
                    from ..widgets.charts.common.cache_dpr import exporting as _exporting
                    if _exporting():
                        _orig(event)
                        return
                except Exception:
                    log_swallowed()
                if cache is not None and self._progress >= 1.0:
                    if cache.size() == self.size():
                        from aqt.qt import QPainter
                        p = QPainter(self)
                        p.drawPixmap(0, 0, cache)
                        p.end()
                        return
                    if self._is_resizing:
                        # Interactive resizing fires many resize/paint pairs per second, and a full
                        # repaint of every open chart on each one lags. Show the last good frame
                        # stretched to the new size and defer the real re-render until resizing
                        # settles (see the resizeEvent wrapper and _on_resize_settled()).
                        from aqt.qt import QPainter
                        p = QPainter(self)
                        p.drawPixmap(self.rect(), cache)
                        p.end()
                        return
                _orig(event)
                # Capture the idle frame lazily: grabbing it after every animation costs a second
                # full render per chart. Only capture on the second idle paint, when Qt repaints the
                # same idle chart (scroll, expose).
                if self._progress >= 1.0 and cache is None:
                    n = getattr(self, "_idle_paint_count", 0) + 1
                    self._idle_paint_count = n
                    if n == 2:
                        QTimer.singleShot(0, self._capture_idle_cache)
            self.paintEvent = _cached_pe
            self._paintEvent_cache_installed = True

        # Drop the idle-frame cache on any explicit update()/repaint() from Python (zoom, hover,
        # legend and option toggles), otherwise the next paint serves a stale frame. Qt-internal
        # repaints (scroll, expose) still use the cache, and a fresh one is captured once the chart
        # has been idle briefly.
        if not getattr(self, "_update_cache_hook_installed", False):
            _orig_update = self.update
            _orig_repaint = self.repaint

            def _invalidating_update(*args, _orig=_orig_update):
                self._invalidate_idle_frame_cache()
                return _orig(*args)

            def _invalidating_repaint(*args, _orig=_orig_repaint):
                self._invalidate_idle_frame_cache()
                return _orig(*args)

            self.update = _invalidating_update
            self.repaint = _invalidating_repaint
            self._update_cache_hook_installed = True

        # Wrap resizeEvent on the instance rather than in a mixin method: several charts define
        # their own resizeEvent, which would shadow a mixin method via the MRO. Same approach as for
        # paintEvent above.
        if not getattr(self, "_resizeEvent_debounce_installed", False):
            _orig_re = self.resizeEvent
            def _debounced_re(event, _orig=_orig_re):
                _orig(event)
                # Mark the chart as resizing so paintEvent serves the cheap scaled frame (see _cached_pe), and do the real re-render ~120ms after the last resize tick.
                self._is_resizing = True
                timer = self._resize_debounce_timer
                if timer is None:
                    timer = QTimer(self)
                    timer.setSingleShot(True)
                    timer.timeout.connect(self._on_resize_settled)
                    self._resize_debounce_timer = timer
                timer.start(120)
            self.resizeEvent = _debounced_re
            self._resizeEvent_debounce_installed = True

    def _on_data_animation_finished(self):
        if self._is_data_animating:
            ChartAnimationMixin._active_data_animation_count = max(
                0, ChartAnimationMixin._active_data_animation_count - 1
            )
            self._is_data_animating = False
            self._viewport_skip_count = 0
            self._force_repaint_current_animation = False
            self._idle_paint_count = 0

    def _invalidate_idle_frame_cache(self):
        if getattr(self, "_capturing_cache", False):
            return
        self._idle_frame_cache = None
        # The next two idle paints re-arm the lazy capture (see _cached_pe).
        self._idle_paint_count = 0

    def _capture_idle_cache(self):
        """Capture current rendered frame to QPixmap for idle-state cache serving."""
        if self._progress < 1.0 or not self.isVisible():
            return
        if self.width() <= 0 or self.height() <= 0:
            return
        timer = getattr(self, "_idle_recapture_timer", None)
        if timer is not None and timer.isActive():
            timer.stop()
        self._capturing_cache = True
        try:
            # The chart alone, without its child widgets (zoom scroll bar, labels): they are
            # painted over the cached frame again, and a semi-transparent one baked into it
            # would show twice (darker) as soon as the cache is served.
            from aqt.qt import QPixmap, QPoint, QRegion, QWidget, Qt as _Qt

            dpr = self.devicePixelRatioF() or 1.0
            px = QPixmap(max(1, int(round(self.width() * dpr))), max(1, int(round(self.height() * dpr))))
            px.setDevicePixelRatio(dpr)
            px.fill(_Qt.GlobalColor.transparent)
            self.render(px, QPoint(0, 0), QRegion(), QWidget.RenderFlag.DrawWindowBackground)
            if not px.isNull():
                self._idle_frame_cache = px
        except Exception:
            log_swallowed()
        finally:
            self._capturing_cache = False

    def _get_pinned_animation_key(self):
        return getattr(self, "_pinned_widget_id", None)

    def _animation_scope(self):
        if bool(getattr(self, "_pinned_widget_id", None)):
            return "pinned"
        if bool(getattr(self, "is_pinned", False)):
            return "pinned"
        owner = str(getattr(self, "_chart_owner", "") or "").strip().lower()
        if owner.startswith("pinned"):
            return "pinned"
        # Some pinned composites (e.g. activity stack) wrap child charts inside
        # a parent container that carries the pinned widget id.
        p = getattr(self, "parentWidget", lambda: None)()
        while p is not None:
            if bool(getattr(p, "_pinned_widget_id", None)):
                return "pinned"
            p = p.parentWidget()
        return "details"

    def _has_meaningful_data_for_animation(self):
        # Best-effort check so the first animation can wait until data exists.
        # Skeleton payloads (all zeros) must not consume the one-shot intro.
        def _has_non_zero_number(obj, depth=0, max_depth=8):
            if depth > max_depth or obj is None:
                return False
            if isinstance(obj, bool):
                return False
            if isinstance(obj, (int, float)):
                return abs(float(obj)) > 1e-12
            if isinstance(obj, dict):
                for v in obj.values():
                    if _has_non_zero_number(v, depth + 1, max_depth):
                        return True
                return False
            if isinstance(obj, (list, tuple, set)):
                for v in obj:
                    if _has_non_zero_number(v, depth + 1, max_depth):
                        return True
                return False
            return False

        try:
            if hasattr(self, "data_list"):
                return _has_non_zero_number(getattr(self, "data_list", None))
            if hasattr(self, "retention_data"):
                data = getattr(self, "retention_data", None)
                return _has_non_zero_number(data)
            if hasattr(self, "data_dict"):
                return _has_non_zero_number(getattr(self, "data_dict", None))
            if hasattr(self, "data"):
                return _has_non_zero_number(getattr(self, "data", None))
            if hasattr(self, "counts"):
                return _has_non_zero_number(getattr(self, "counts", None))
        except Exception:
            return True
        return True

    def _finish_without_animation(self):
        animation = getattr(self, "animation", None)
        if animation is not None:
            animation.stop()
        self._progress = 1.0
        self.update()

    def maybe_start_initial_animation(self):
        # For non-pinned charts only: if first show already happened before data was ready,
        # trigger the one-shot animation when data becomes available.
        if self._get_pinned_animation_key():
            return
        if self._initial_animation_done:
            return
        if not self._has_meaningful_data_for_animation():
            return
        if not self.isVisible():
            return
        self._initial_animation_done = True
        self.replay_animation()

    @pyqtProperty(float)
    def progress(self):
        return self._progress

    @progress.setter
    def progress(self, val):
        self._progress = val
        # The driver handles repaint and viewport skipping during animation; direct callers call self.update() where needed.

    def get_progress(self):
        return self._progress

    def set_progress(self, val):
        self.progress = val

    def showEvent(self, event):
        if hasattr(super(), "showEvent"):
            super().showEvent(event)
        if not chart_animations_allowed(self):
            self._finish_without_animation()
            return
        animation = getattr(self, "animation", None)
        if animation is None:
            self._progress = 1.0
            return
        # External container transitions (fade in/out for pinned show/hide) can request
        # skipping the chart intro animation once to avoid double-animation cost.
        try:
            skip_once = bool(self.property("deepdivestats_skip_next_show_anim"))
        except Exception:
            skip_once = False
        if skip_once:
            try:
                self.setProperty("deepdivestats_skip_next_show_anim", False)
            except Exception:
                log_swallowed()
            self._finish_without_animation()
            return
        if animation.state() == QAbstractAnimation.State.Running:
            return
        key = self._get_pinned_animation_key()
        if key:
            if key in ChartAnimationMixin._pinned_animated_ids:
                # If a data transition is active when the pinned page becomes visible
                # again, replay the transition animation instead of snapping to end.
                if bool(getattr(self, "_data_transition_active", False)):
                    self.replay_animation_coalesced()
                    return
                self._finish_without_animation()
                return
            ChartAnimationMixin._pinned_animated_ids.add(key)
            self.replay_animation()
            return

        # Default behavior (Deep Dive / non-pinned):
        # animate only once on first meaningful display of this widget instance.
        if self._initial_animation_done:
            if self.animation.state() == QAbstractAnimation.State.Running:
                return
            self._finish_without_animation()
            return
        if self._has_meaningful_data_for_animation():
            self._initial_animation_done = True
            self.replay_animation()

    def replay_animation(self):
        if not chart_animations_allowed(self):
            self._finish_without_animation()
            return
        animation = getattr(self, "animation", None)
        if animation is None:
            self._progress = 1.0
            self.update()
            return
        animation.stop()
        self._progress = 0.0
        try:
            animation.setCurrentTime(0)
        except Exception:
            log_swallowed()
        animation.start()

    def replay_animation_coalesced(self):
        """Replay now, or finish at once when animations are off."""
        if not chart_animations_allowed(self):
            self._finish_without_animation()
            return
        self.replay_animation()

    @staticmethod
    def _is_number(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    @classmethod
    def _flatten_numeric_payload(cls, payload):
        """Pull the numeric values out of a chart payload.

        Handles (label, value) tuples, stacked dict rows (sums the numbers) and raw
        numbers.
        """
        if payload is None:
            return []
        out = []
        if not isinstance(payload, (list, tuple)):
            return out
        for item in payload:
            if cls._is_number(item):
                out.append(float(item))
                continue
            if isinstance(item, (list, tuple)):
                if len(item) >= 2 and cls._is_number(item[1]):
                    out.append(float(item[1]))
                continue
            if isinstance(item, dict):
                row_sum = 0.0
                for k, v in item.items():
                    if isinstance(k, str):
                        lk = k.lower()
                        if "date" in lk or "label" in lk:
                            continue
                    if cls._is_number(v):
                        row_sum += float(v)
                out.append(row_sum)
        return out

    def animate_data_update(
        self,
        old_payload,
        new_payload,
        *,
        min_duration_ms=140,
        max_duration_ms=340,
        empty_transition_duration_ms=220,
    ):
        """
        Shared update animation for charts.
        Uses a fixed duration per callsite instead of scaling to data delta.
        """
        if not chart_animations_allowed(self):
            self._finish_without_animation()
            return False
        self._idle_frame_cache = None
        self._idle_paint_count = 0
        old_vals = self._flatten_numeric_payload(old_payload)
        new_vals = self._flatten_numeric_payload(new_payload)
        max_len = max(len(old_vals), len(new_vals))
        if max_len == 0:
            self.animation.stop()
            self._progress = 1.0
            self.update()
            return False

        if len(old_vals) < max_len:
            old_vals += [0.0] * (max_len - len(old_vals))
        if len(new_vals) < max_len:
            new_vals += [0.0] * (max_len - len(new_vals))

        old_total = sum(abs(v) for v in old_vals)
        new_total = sum(abs(v) for v in new_vals)

        old_has_data = old_total > 0.0
        new_has_data = new_total > 0.0
        is_empty_transition = (old_has_data != new_has_data)
        first_data_fill = (
            (not bool(getattr(self, "_initial_animation_done", False)))
            and (not old_has_data)
            and new_has_data
        )

        # First meaningful payload should not replay a second transition animation.
        # Let the one-shot intro animation (if any) own the initial reveal.
        if first_data_fill:
            try:
                self.maybe_start_initial_animation()
            except Exception:
                log_swallowed()
            self.update()
            return False

        if is_empty_transition:
            duration = int(empty_transition_duration_ms)
            easing = QEasingCurve.Type.InOutSine
        else:
            duration = int(round((float(min_duration_ms) + float(max_duration_ms)) / 2.0))
            easing = QEasingCurve.Type.InOutCubic
        active = ChartAnimationMixin._active_data_animation_count
        if not self._is_data_animating:
            ChartAnimationMixin._active_data_animation_count += 1
            active += 1
            self._is_data_animating = True
        self._force_repaint_current_animation = bool(
            chart_animation_force_repaint_requested(self)
        )
        self.animation.setDuration(max(1, duration))
        self.animation.setEasingCurve(easing)
        self.animation.stop()
        self._progress = 0.0
        self.update()
        self.replay_animation_coalesced()
        return True

    @staticmethod
    def interpolate_scalar(old_value, new_value, t):
        ov = float(old_value or 0.0)
        nv = float(new_value or 0.0)
        tt = t * t * (3.0 - (2.0 * t))  # smootherstep
        return ov + ((nv - ov) * tt)

    @staticmethod
    def interpolate_numeric_series(old_values, new_values, t, align_right=False):
        old_values = [float(v) for v in (old_values or [])]
        new_values = [float(v) for v in (new_values or [])]
        n = max(len(old_values), len(new_values))
        if len(old_values) < n:
            pad = [0.0] * (n - len(old_values))
            old_values = (pad + old_values) if align_right else (old_values + pad)
        if len(new_values) < n:
            pad = [0.0] * (n - len(new_values))
            new_values = (pad + new_values) if align_right else (new_values + pad)
        return [max(0.0, ChartAnimationMixin.interpolate_scalar(ov, nv, t)) for ov, nv in zip(old_values, new_values)]

    @staticmethod
    def interpolate_stacked_rows(old_rows, new_rows, series_keys, t, align_right=False):
        old_rows = list(old_rows or [])
        new_rows = list(new_rows or [])
        n = max(len(old_rows), len(new_rows))
        if len(old_rows) < n:
            pad = [{} for _ in range(n - len(old_rows))]
            old_rows = (pad + old_rows) if align_right else (old_rows + pad)
        if len(new_rows) < n:
            pad = [{} for _ in range(n - len(new_rows))]
            new_rows = (pad + new_rows) if align_right else (new_rows + pad)
        out = []
        for i in range(n):
            old_item = old_rows[i]
            new_item = new_rows[i]
            row = {"pretty_date": new_item.get("pretty_date", old_item.get("pretty_date", ""))}
            for key in series_keys:
                ov = float(old_item.get(key, 0) or 0)
                nv = float(new_item.get(key, 0) or 0)
                row[key] = max(0.0, ChartAnimationMixin.interpolate_scalar(ov, nv, t))
            out.append(row)
        return out

    @staticmethod
    def interpolate_bar_slots(
        old_count,
        new_count,
        t,
        plot_left,
        plot_width,
        align_right=False,
        width_ratio=0.8,
    ):
        """
        Return per-slot (center_x, bar_width) interpolated from old->new layouts.
        Useful when count changes and bars should slide smoothly instead of snapping.
        """
        old_count = int(old_count or 0)
        new_count = int(new_count or 0)
        n = max(old_count, new_count)
        if n <= 0:
            return []

        old_step = plot_width / max(1, old_count)
        new_step = plot_width / max(1, new_count)
        old_pad = (n - old_count) if align_right else 0
        new_pad = (n - new_count) if align_right else 0

        slots = []
        for i in range(n):
            old_slot = i - old_pad if align_right else i
            new_slot = i - new_pad if align_right else i
            old_exists = 0 <= old_slot < old_count
            new_exists = 0 <= new_slot < new_count

            if old_exists:
                old_center = plot_left + ((old_slot + 0.5) * old_step)
                old_width = old_step * width_ratio
            else:
                # Right-aligned time-span transitions add/remove on the left side.
                old_center = (plot_left - (new_step * 0.5)) if align_right else (plot_left + plot_width + (old_step * 0.5))
                old_width = max(1.0, new_step * 0.2)

            if new_exists:
                new_center = plot_left + ((new_slot + 0.5) * new_step)
                new_width = new_step * width_ratio
            else:
                new_center = (plot_left - (old_step * 0.5)) if align_right else (plot_left + plot_width + (new_step * 0.5))
                new_width = max(1.0, old_step * 0.2)

            center = old_center + ((new_center - old_center) * t)
            width = old_width + ((new_width - old_width) * t)
            slots.append((center, max(1.0, width)))
        return slots

    @staticmethod
    def interpolate_line_x_positions(old_count, new_count, t, plot_left, plot_width, align_right=False):
        """
        Return interpolated x positions for line-like overlays when point count changes.
        """
        old_count = int(old_count or 0)
        new_count = int(new_count or 0)
        n = max(old_count, new_count)
        if n <= 0:
            return []

        old_pad = (n - old_count) if align_right else 0
        new_pad = (n - new_count) if align_right else 0
        xs = []
        for i in range(n):
            old_slot = i - old_pad if align_right else i
            new_slot = i - new_pad if align_right else i
            old_exists = 0 <= old_slot < old_count
            new_exists = 0 <= new_slot < new_count

            if old_exists:
                old_x = (
                    plot_left + (plot_width * old_slot / (old_count - 1))
                    if old_count > 1 else (plot_left + (plot_width * 0.5))
                )
            else:
                old_x = plot_left - (plot_width * 0.05)

            if new_exists:
                new_x = (
                    plot_left + (plot_width * new_slot / (new_count - 1))
                    if new_count > 1 else (plot_left + (plot_width * 0.5))
                )
            else:
                new_x = plot_left - (plot_width * 0.05)

            xs.append(old_x + ((new_x - old_x) * t))
        return xs

    def hideEvent(self, event):
        animation = getattr(self, "animation", None)
        if animation is not None:
            animation.stop()
        timer = getattr(self, "_resize_debounce_timer", None)
        if timer is not None:
            timer.stop()
        self._is_resizing = False
        if hasattr(super(), "hideEvent"):
            super().hideEvent(event)

    def _on_resize_settled(self):
        self._is_resizing = False
        self.update()



