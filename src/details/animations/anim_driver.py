# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Single 60 FPS timer shared by all chart animations.

One QTimer drives every chart instead of one QPropertyAnimation per chart, and
all update() calls land in the same tick so Qt can batch the repaints.
"""

import time

from aqt.qt import QAbstractAnimation, QEasingCurve, QObject, QTimer
from .chart_policy import (
    MIN_VISIBLE_CHART_FRACTION,
    chart_animation_force_repaint_allowed,
    chart_animation_queue_limit,
    chart_animation_queue_plan,
    chart_visible_fraction,
)
from ..logic.logger import log_swallowed


# Pure-Python easing functions (avoids QEasingCurve.valueForProgress overhead)

def _ease(t, etype):
    if etype == QEasingCurve.Type.OutQuart:
        u = 1.0 - t
        return 1.0 - u * u * u * u
    if etype == QEasingCurve.Type.InOutCubic:
        if t < 0.5:
            return 4.0 * t * t * t
        u = -2.0 * t + 2.0
        return 1.0 - u * u * u * 0.5
    if etype == QEasingCurve.Type.OutCubic:
        u = 1.0 - t
        return 1.0 - u * u * u
    if etype == QEasingCurve.Type.InOutSine:
        import math
        return -(math.cos(math.pi * t) - 1.0) * 0.5
    return t


# Minimal signal-like object for animation.finished.connect() compatibility

class _FinishedProxy:
    __slots__ = ("_cbs",)

    def __init__(self):
        self._cbs = []

    def connect(self, fn):
        self._cbs.append(fn)

    def emit(self):
        for cb in list(self._cbs):
            try:
                cb()
            except Exception:
                log_swallowed()


# Drop-in replacement for QPropertyAnimation driven by the shared timer

class _AnimProxy:
    """Stands in for QPropertyAnimation with the methods ChartAnimationMixin uses:
    setDuration, setEasingCurve, setStartValue, setEndValue, setCurrentTime, stop,
    start, state and finished.
    """
    __slots__ = ("_chart", "_duration", "_easing", "finished")

    def __init__(self, chart, duration=500, easing=QEasingCurve.Type.OutQuart):
        self._chart = chart
        self._duration = max(1, int(duration))
        self._easing = easing
        self.finished = _FinishedProxy()

    def setDuration(self, ms):
        self._duration = max(1, int(ms))

    def setEasingCurve(self, easing):
        # Accept both QEasingCurve instance and QEasingCurve.Type enum
        if isinstance(easing, QEasingCurve):
            self._easing = easing.type()
        else:
            self._easing = easing

    def setStartValue(self, v):
        pass  # Always 0 to 1; the driver handles it

    def setEndValue(self, v):
        pass

    def setCurrentTime(self, t):
        pass  # Driver handles restart from t=0 on each start()

    def stop(self):
        _driver.cancel(self._chart)

    def start(self):
        _driver.register(self._chart, self._duration, self._easing, self.finished)

    def state(self):
        return (
            QAbstractAnimation.State.Running
            if _driver.is_running(self._chart)
            else QAbstractAnimation.State.Stopped
        )


# The single shared QTimer that drives all chart animations

class _GlobalAnimDriver(QObject):
    _TICK_MS = 16
    _QUEUE_OVERLAP_PROGRESS = 0.35
    _QUEUE_OVERLAP_SLOTS = 1

    def __init__(self):
        super().__init__()
        # {id(chart): (chart, root_key, start_monotonic, duration_ms, easing, finished_proxy, queue_plan)}
        self._entries = {}
        # {id(chart): (chart, root_key, duration_ms, easing, finished_proxy, max_concurrent, queue_plan)}
        self._pending = {}
        self._timer = QTimer()
        self._timer.setInterval(self._TICK_MS)
        self._timer.timeout.connect(self._tick)

    def register(self, chart, duration_ms, easing, finished_proxy):
        """Start now, or queue softly when a grouped batch is over budget."""
        cid = id(chart)
        root_key = self._root_key(chart)
        queue_plan = chart_animation_queue_plan(chart)
        max_concurrent = max(0, int(chart_animation_queue_limit(chart) or 0))
        duration_ms = max(1, int(duration_ms))

        if cid in self._pending:
            self._pending.pop(cid, None)

        if cid in self._entries:
            self._entries[cid] = (chart, root_key, None, duration_ms, easing, finished_proxy, queue_plan)
            if not self._timer.isActive():
                self._timer.start()
            return

        if queue_plan is not None:
            self._pending[cid] = (chart, root_key, duration_ms, easing, finished_proxy, 0, queue_plan)
            self._try_start_pending_for_root(root_key)
            return

        if max_concurrent > 0 and self._active_count_for_root(root_key) >= max_concurrent:
            self._pending[cid] = (chart, root_key, duration_ms, easing, finished_proxy, max_concurrent, None)
            return

        self._start_entry(chart, root_key, duration_ms, easing, finished_proxy, queue_plan=None)

    def cancel(self, chart):
        """Remove chart from driver without firing finished callbacks."""
        cid = id(chart)
        entry = self._entries.pop(cid, None)
        self._pending.pop(cid, None)
        if entry:
            _, root_key, _, _, _, _, _ = entry
            self._try_start_pending_for_root(root_key)
        if not self._entries:
            self._timer.stop()

    def is_running(self, chart):
        cid = id(chart)
        return (cid in self._entries) or (cid in self._pending)

    def _root_key(self, chart):
        try:
            root = chart.window() or chart
        except Exception:
            root = chart
        return id(root)

    def _active_count_for_root(self, root_key):
        count = 0
        for _, entry_root_key, _, _, _, _, _ in self._entries.values():
            if entry_root_key == root_key:
                count += 1
        return count

    def _active_entries_for_root(self, root_key):
        out = []
        for entry in self._entries.values():
            if entry[1] == root_key:
                out.append(entry)
        return out

    def _oldest_progress_for_root(self, root_key, now):
        progress = 0.0
        for _, entry_root_key, t0, dur_ms, _, _, _ in self._entries.values():
            if entry_root_key != root_key or t0 is None:
                continue
            try:
                raw_t = ((now - t0) * 1000.0) / max(1, int(dur_ms))
            except Exception:
                raw_t = 0.0
            progress = max(progress, max(0.0, min(1.0, float(raw_t))))
        return progress

    def _start_entry(self, chart, root_key, duration_ms, easing, finished_proxy, queue_plan=None):
        # The clock starts on the first frame (see _tick), not now.
        self._entries[id(chart)] = (
            chart,
            root_key,
            None,
            max(1, int(duration_ms)),
            easing,
            finished_proxy,
            queue_plan,
        )
        if not self._timer.isActive():
            self._timer.start()

    def _next_pending_wave_group(self, root_key):
        wave_entries = []
        for cid, entry in self._pending.items():
            chart, pending_root_key, duration_ms, easing, finished_proxy, max_concurrent, queue_plan = entry
            if pending_root_key != root_key or queue_plan is None:
                continue
            wave_entries.append(
                (
                    int(queue_plan.get("batch_key", 0) or 0),
                    int(queue_plan.get("wave_index", 0) or 0),
                    int(queue_plan.get("order_index", 0) or 0),
                    cid,
                    entry,
                )
            )
        if not wave_entries:
            return []
        wave_entries.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
        first_batch_key, first_wave_index = wave_entries[0][0], wave_entries[0][1]
        return [item for item in wave_entries if item[0] == first_batch_key and item[1] == first_wave_index]

    def _wave_group_can_start(self, root_key, batch_key, wave_index, now):
        has_pending_lower_wave = False
        lower_wave_progress = 1.0
        has_active_lower_wave = False

        for _, entry in self._pending.items():
            _, pending_root_key, _, _, _, _, queue_plan = entry
            if pending_root_key != root_key or queue_plan is None:
                continue
            if int(queue_plan.get("batch_key", 0) or 0) != int(batch_key):
                continue
            if int(queue_plan.get("wave_index", 0) or 0) < int(wave_index):
                has_pending_lower_wave = True
                break
        if has_pending_lower_wave:
            return False

        for _, entry_root_key, t0, dur_ms, _, _, queue_plan in self._entries.values():
            if entry_root_key != root_key or queue_plan is None:
                continue
            if int(queue_plan.get("batch_key", 0) or 0) != int(batch_key):
                continue
            if int(queue_plan.get("wave_index", 0) or 0) >= int(wave_index):
                continue
            has_active_lower_wave = True
            if t0 is None:
                lower_wave_progress = 0.0
                continue
            try:
                raw_t = ((now - t0) * 1000.0) / max(1, int(dur_ms))
            except Exception:
                raw_t = 0.0
            lower_wave_progress = min(lower_wave_progress, max(0.0, min(1.0, float(raw_t))))

        if not has_active_lower_wave:
            return True
        return lower_wave_progress >= self._QUEUE_OVERLAP_PROGRESS

    def _try_start_pending_for_root(self, root_key, now=None):
        if now is None:
            now = time.monotonic()
        while True:
            started = False
            wave_group = self._next_pending_wave_group(root_key)
            if wave_group:
                batch_key, wave_index = wave_group[0][0], wave_group[0][1]
                if self._wave_group_can_start(root_key, batch_key, wave_index, now):
                    for _, _, _, cid, entry in wave_group:
                        chart, pending_root_key, duration_ms, easing, finished_proxy, _, queue_plan = entry
                        self._pending.pop(cid, None)
                        self._start_entry(
                            chart,
                            pending_root_key,
                            duration_ms,
                            easing,
                            finished_proxy,
                            queue_plan=queue_plan,
                        )
                        started = True
                if started:
                    continue

            active_entries = self._active_entries_for_root(root_key)
            active_count = len(active_entries)
            for cid, (chart, pending_root_key, duration_ms, easing, finished_proxy, max_concurrent, queue_plan) in list(self._pending.items()):
                if pending_root_key != root_key:
                    continue
                if queue_plan is not None:
                    continue
                base_limit = max(1, int(max_concurrent))
                if active_count < base_limit:
                    self._pending.pop(cid, None)
                    self._start_entry(chart, pending_root_key, duration_ms, easing, finished_proxy, queue_plan=None)
                    started = True
                    break
                overflow_slots_used = max(0, active_count - base_limit)
                oldest_progress = self._oldest_progress_for_root(root_key, now)
                if (
                    active_count == base_limit
                    and overflow_slots_used < self._QUEUE_OVERLAP_SLOTS
                    and oldest_progress >= self._QUEUE_OVERLAP_PROGRESS
                ):
                    self._pending.pop(cid, None)
                    self._start_entry(chart, pending_root_key, duration_ms, easing, finished_proxy, queue_plan=None)
                    started = True
                    break
                if active_count >= base_limit:
                    return
            if not started:
                return

    def _tick(self):
        if not self._entries:
            self._timer.stop()
            return

        now = time.monotonic()
        done_cids = set()
        freed_root_keys = set()

        for cid, (chart, root_key, t0, dur_ms, easing, fin, queue_plan) in list(self._entries.items()):
            if t0 is None:
                # First frame: the clock starts here. Started while the window was busy
                # (building the other charts), the animation would otherwise have used up
                # part of its time before showing anything, and looked faster than the rest.
                t0 = now
                self._entries[cid] = (chart, root_key, t0, dur_ms, easing, fin, queue_plan)
            elapsed_ms = (now - t0) * 1000.0
            raw_t = elapsed_ms / dur_ms
            if raw_t >= 1.0:
                raw_t = 1.0
                done_cids.add(cid)

            t = _ease(raw_t, easing)
            try:
                chart._progress = t
                if chart.isVisible():
                    if (
                        chart_visible_fraction(chart) < MIN_VISIBLE_CHART_FRACTION
                        and not chart_animation_force_repaint_allowed(chart)
                    ):
                        # Skip repaint for off-screen charts
                        chart._viewport_skip_count = getattr(chart, "_viewport_skip_count", 0) + 1
                    else:
                        chart.update()
            except Exception:
                done_cids.add(cid)

        for cid in done_cids:
            entry = self._entries.pop(cid, None)
            if entry:
                _, root_key, _, _, _, fin, _ = entry
                freed_root_keys.add(root_key)
                if fin:
                    fin.emit()

        for root_key in freed_root_keys:
            self._try_start_pending_for_root(root_key, now=now)

        pending_root_keys = {entry[1] for entry in self._pending.values()}
        for root_key in pending_root_keys:
            self._try_start_pending_for_root(root_key, now=now)

        if not self._entries:
            self._timer.stop()


_driver = _GlobalAnimDriver()


# Single shared timer for all StatCardEffect hover animations

class _GlobalHoverDriver(QObject):
    _TICK_MS = 16  # ~60 FPS, aligned with the chart driver

    def __init__(self):
        super().__init__()
        self._effects = {}  # id(effect) -> effect
        self._timer = QTimer()
        self._timer.setInterval(self._TICK_MS)
        self._timer.timeout.connect(self._tick)

    def register(self, effect):
        self._effects[id(effect)] = effect
        if not self._timer.isActive():
            self._timer.start()

    def unregister(self, effect):
        self._effects.pop(id(effect), None)
        if not self._effects:
            self._timer.stop()

    def _tick(self):
        if not self._effects:
            self._timer.stop()
            return
        done = []
        for eid, effect in list(self._effects.items()):
            try:
                still_active = effect._on_global_tick()
                if not still_active:
                    done.append(eid)
            except Exception:
                done.append(eid)
        for eid in done:
            self._effects.pop(eid, None)
        if not self._effects:
            self._timer.stop()


_hover_driver = _GlobalHoverDriver()
