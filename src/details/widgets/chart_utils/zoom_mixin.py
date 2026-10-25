# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""
Mixin for adding zoom functionality to chart widgets.
Supports mouse wheel zoom (Ctrl+Scroll) and click-drag selection zoom.
"""
from aqt.qt import Qt, QRect, QColor, QPen, pyqtSignal, QObject, QScrollBar
from ...ui.theme import get_scrollbar_style
from .theme import get_theme_colors
from .binning import get_bin_size
from ....qss import set_qss


class ZoomableChartSignals(QObject):
    """Signals for zoom changes - separated to allow multiple inheritance."""
    zoom_changed = pyqtSignal(bool, int, int)  # is_zoomed, start_idx, end_idx
    # Zoom-out asked while the whole range is already shown (lets the 10-minute
    # view go back to daily data).
    zoom_out_limit = pyqtSignal()


from contextlib import contextmanager
from ...logic.logger import log_swallowed
from . import zoom_camera


def zoom_rows(chart):
    """Rows the zoom indices refer to (activity-like charts or the retention chart)."""
    rows = getattr(chart, "_full_data", None)
    if rows is None:
        ret = getattr(chart, "_full_retention_data", None)
        if isinstance(ret, dict):
            rows = ret.get("all") or next((v for v in ret.values() if v), None)
    return rows if isinstance(rows, (list, tuple)) else []


def _row_label(row):
    if isinstance(row, (list, tuple)):
        return row[0] if row else None
    if isinstance(row, dict):
        for k in ("label", "date", "logical_date", "x"):
            if row.get(k) is not None:
                return row.get(k)
    return None


def zoom_snapshot(chart):
    """(start, end, length, first_label, last_label) of the current zoom window."""
    rows = zoom_rows(chart)
    start, end = int(chart._zoom_start), int(chart._zoom_end)
    first = _row_label(rows[start]) if 0 <= start < len(rows) else None
    last = _row_label(rows[end - 1]) if 0 < end <= len(rows) else None
    return (start, end, len(rows), first, last)


def remap_zoom(snapshot, new_rows):
    """Where the same zoom window sits in new_rows, or None if it cannot be kept.

    Matches by label (date) first, then by index when the row count is unchanged.
    """
    start, end, length, first, last = snapshot
    n = len(new_rows or [])
    if n <= 0:
        return None
    if first is not None and last is not None:
        index = {}
        for i, r in enumerate(new_rows):
            index.setdefault(_row_label(r), i)
        ns, ne = index.get(first), index.get(last)
        if ns is not None and ne is not None and ne + 1 - ns >= 2:
            return ns, ne + 1
    if n == length and end > start:
        return start, end
    return None


@contextmanager
def preserve_zoom(*charts, notify=False):
    """Keep the zoom window of charts across an in-place data update.

    update_data() resets the zoom, which is wrong when only the metric or the deck
    changes over the same dates. Zoom signals are held back during the swap so
    linked charts do not see a reset followed by a re-zoom.
    """
    states = []
    for c in charts:
        if c is None:
            continue
        try:
            if not bool(getattr(c, "_is_zoomed", False)):
                continue
            sig = getattr(c, "_zoom_signals", None)
            if sig is None:
                continue
            snap = zoom_snapshot(c)
            anchor = getattr(c, "_zoom_anchor", None)
            if anchor and anchor[1] == (snap[3], snap[4]):
                # Still the window set by the last restore (the user did not touch it):
                # remap from the original labels so bin snapping cannot make it drift.
                snap = anchor[0]
            states.append((c, sig, sig.blockSignals(True), snap))
            c._keep_zoom = snap
        except Exception:
            continue
    try:
        yield
    finally:
        for c, sig, prev, snap in states:
            restored = False
            c._keep_zoom = None
            try:
                target = remap_zoom(snap, zoom_rows(c))
                if target:
                    if (int(c._zoom_start), int(c._zoom_end)) != tuple(target):
                        c.set_zoom_range(*target)
                    restored = True
                    now = zoom_snapshot(c)
                    c._zoom_anchor = (snap, (now[3], now[4]))
            except Exception:
                restored = False
            sig.blockSignals(prev)
            if not restored:
                try:
                    sig.zoom_changed.emit(False, 0, int(getattr(c, "_zoom_end", 0) or 0))
                except Exception:
                    log_swallowed()
            elif notify:
                # Zoom kept, but the data under it changed: let headers / linked charts refresh.
                try:
                    sig.zoom_changed.emit(True, int(c._zoom_start), int(c._zoom_end))
                except Exception:
                    log_swallowed()


class ZoomableMixin:
    """Adds zoom to a chart widget.

        class MyChart(ZoomableMixin, QWidget):
            def __init__(self, data):
                super().__init__()
                self.init_zoom(len(data))

            def paintEvent(self, event):
                visible = self.get_visible_data(self.data)

            def resizeEvent(self, event):
                super().resizeEvent(event)
                self.update_scrollbar_geometry()
    """

    def _get_zoom_snap_step(self, span=None):
        """Return index snap step for zoom/pan; >1 when adaptive binning is active."""
        try:
            if not bool(getattr(self, "binning_active", False)):
                return 1
            base_span = int(span if span is not None else (self._zoom_end - self._zoom_start))
            if base_span <= 0:
                base_span = int(getattr(self, "_full_length", 0) or 0)
            return max(1, int(get_bin_size(max(1, base_span))))
        except Exception:
            return 1

    @staticmethod
    def _snap_down(value, step):
        if step <= 1:
            return int(value)
        return int(value) - (int(value) % int(step))

    @staticmethod
    def _snap_up(value, step):
        if step <= 1:
            return int(value)
        v = int(value)
        return v if (v % int(step) == 0) else (v + (int(step) - (v % int(step))))

    def init_zoom(self, data_length):
        """Initialize zoom state. Call in __init__ after super()."""
        # Do not re-create signals or scrollbars if already initialized
        if hasattr(self, "_zoom_signals") and self._zoom_signals:
            self.update_data_length(data_length)
            # Plain reset: charts override reset_zoom() with a zoom-out animation, which must
            # not run (or clobber the transition state) in the middle of a data update.
            ZoomableMixin.reset_zoom(self)
            return

        self._zoom_signals = ZoomableChartSignals()
        self.zoom_changed = self._zoom_signals.zoom_changed
        self.zoom_out_limit = self._zoom_signals.zoom_out_limit

        self._full_length = data_length
        self._zoom_start = 0
        self._zoom_end = data_length
        self._is_zoomed = False

        self._selecting = False

        self._scrollbar = QScrollBar(Qt.Orientation.Horizontal, self)
        set_qss(self._scrollbar, get_scrollbar_style(bool(get_theme_colors(self).get("is_dark"))))
        self._scrollbar.hide()
        self._scrollbar.valueChanged.connect(self._on_scrollbar_value_changed)

        # Ignore the wheel on the internal scrollbar so it does not swallow page scrolling.
        def ignore_wheel(event):
            event.ignore()
        self._scrollbar.wheelEvent = ignore_wheel

        self.setMouseTracking(True)

    def _on_scrollbar_value_changed(self, value):
        """Handle scrollbar movement to pan chart."""
        if not self._is_zoomed:
            return

        visible_range = self._zoom_end - self._zoom_start
        step = self._get_zoom_snap_step(visible_range)
        new_start = self._snap_down(value, step)
        new_end = new_start + visible_range

        if new_start < 0:
            new_start = 0
            new_end = visible_range
        if new_end > self._full_length:
            new_end = self._full_length
            new_start = new_end - visible_range

        if new_start != self._zoom_start:
            self.set_zoom_range(new_start, new_end)

    def update_scrollbar_geometry(self):
        """Update scrollbar position and size. Call in resizeEvent."""
        if hasattr(self, '_scrollbar') and self._scrollbar:
            h = 6 # scrollbar height
            self._scrollbar.setGeometry(0, self.height() - h, self.width(), h)

    def set_zoom_range(self, start_idx, end_idx):
        """Set a specific zoom range."""
        zoom_camera.touch(self)
        if start_idx < 0:
            start_idx = 0
        if end_idx > self._full_length:
            end_idx = self._full_length
        step = self._get_zoom_snap_step(end_idx - start_idx)
        if step > 1:
            start_idx = self._snap_down(start_idx, step)
            end_idx = self._snap_up(end_idx, step)
            if end_idx > self._full_length:
                end_idx = self._full_length
            if start_idx >= end_idx:
                start_idx = max(0, end_idx - step)
        min_span = max(2, step)
        if end_idx - start_idx < min_span:
            return

        self._zoom_start = int(start_idx)
        self._zoom_end = int(end_idx)
        self._is_zoomed = (start_idx != 0 or end_idx != self._full_length)

        if hasattr(self, '_scrollbar') and self._scrollbar:
            self._scrollbar.blockSignals(True)
            if self._is_zoomed:
                visible_len = self._zoom_end - self._zoom_start
                self._scrollbar.setMinimum(0)
                self._scrollbar.setMaximum(self._full_length - visible_len)
                self._scrollbar.setPageStep(visible_len)
                self._scrollbar.setSingleStep(max(1, self._get_zoom_snap_step(visible_len)))
                self._scrollbar.setValue(self._zoom_start)
                self._scrollbar.show()
            else:
                self._scrollbar.hide()
            self._scrollbar.blockSignals(False)

        self._zoom_signals.zoom_changed.emit(self._is_zoomed, self._zoom_start, self._zoom_end)
        self.update()

    @property
    def is_zoomed(self):
        return self._is_zoomed

    def get_zoom_range(self):
        """Returns (start_index, end_index) of current zoom."""
        return (self._zoom_start, self._zoom_end)

    def get_visible_data(self, full_data):
        """Slice data to only the visible (zoomed) range."""
        if not self._is_zoomed:
            return full_data
        return full_data[self._zoom_start:self._zoom_end]

    def reset_zoom(self):
        """Reset zoom to show all data."""
        self.set_zoom_range(0, self._full_length)
        self._selecting = False

    def update_data_length(self, new_length):
        """Update the full data length (call when data changes)."""
        self._full_length = new_length
        if self._zoom_end > new_length:
            self._zoom_end = new_length
        if self._zoom_start >= self._zoom_end:
            ZoomableMixin.reset_zoom(self)

    def _x_to_index(self, x, plot_left, plot_width):
        """Convert x pixel position to data index."""
        if plot_width <= 0:
            return 0
        visible_count = self._zoom_end - self._zoom_start
        if visible_count <= 0:
            return self._zoom_start

        relative_x = x - plot_left
        ratio = max(0, min(1, relative_x / plot_width))
        idx = self._zoom_start + int(ratio * visible_count)
        step = self._get_zoom_snap_step(visible_count)
        idx = self._snap_down(idx, step)
        return max(self._zoom_start, min(self._zoom_end - 1, idx))

    def handle_wheel_zoom(self, event, plot_left, plot_width):
        """
        Handle wheel event for zooming. Call from wheelEvent.
        Returns True if event was handled.
        """
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            return self.handle_wheel_pan(event)

        if not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            return False

        delta = event.angleDelta().y()
        if delta == 0:
            return False

        zoom_factor = 0.15  # 15% zoom per scroll step

        cursor_x = event.position().x() if hasattr(event, 'position') else event.pos().x()
        cursor_idx = self._x_to_index(cursor_x, plot_left, plot_width)

        current_range = self._zoom_end - self._zoom_start

        if delta < 0 and current_range >= self._full_length:
            self._zoom_signals.zoom_out_limit.emit()
            event.accept()
            return True

        if delta > 0:
            new_range = max(3, int(current_range * (1 - zoom_factor)))
        else:
            new_range = min(self._full_length, max(current_range + 1, int(current_range * (1 + zoom_factor))))

        if new_range == current_range:
            return True

        cursor_ratio = (cursor_idx - self._zoom_start) / current_range if current_range > 0 else 0.5
        new_start = int(cursor_idx - cursor_ratio * new_range)
        new_end = new_start + new_range

        if new_start < 0:
            new_start = 0
            new_end = new_range
        if new_end > self._full_length:
            new_end = self._full_length
            new_start = max(0, new_end - new_range)

        self.set_zoom_range(new_start, new_end)
        event.accept()
        return True

    def handle_wheel_pan(self, event):
        """
        Handle Shift+Scroll for panning left/right when zoomed.
        Returns True if event was handled.
        """
        if not self._is_zoomed:
            return False

        delta = event.angleDelta().y()
        if delta == 0:
            return False

        current_range = self._zoom_end - self._zoom_start
        step = self._get_zoom_snap_step(current_range)
        # Pan by 10% of visible range per scroll step
        pan_amount = max(step, int(current_range * 0.1))
        if step > 1:
            pan_amount = max(step, self._snap_down(pan_amount, step))

        if delta > 0:
            new_start = self._zoom_start - pan_amount
            new_end = self._zoom_end - pan_amount
        else:
            new_start = self._zoom_start + pan_amount
            new_end = self._zoom_end + pan_amount

        if new_start < 0:
            new_start = 0
            new_end = current_range
        if new_end > self._full_length:
            new_end = self._full_length
            new_start = new_end - current_range

        self.set_zoom_range(new_start, new_end)
        event.accept()
        return True

    def handle_selection_press(self, event, plot_left, plot_width):
        """Handle mouse press for selection zoom. Call from mousePressEvent."""
        if event.button() == Qt.MouseButton.LeftButton:
            x = event.position().x() if hasattr(event, 'position') else event.pos().x()
            if plot_left <= x <= plot_left + plot_width:
                self._selecting = True
                self._selection_start_x = x
                self._selection_end_x = x
                self._selection_start_idx = self._x_to_index(x, plot_left, plot_width)
                self._selection_end_idx = self._selection_start_idx
                return True
        return False

    def handle_selection_move(self, event, plot_left, plot_width):
        """Handle mouse move for selection zoom. Call from mouseMoveEvent."""
        if self._selecting:
            x = event.position().x() if hasattr(event, 'position') else event.pos().x()
            self._selection_end_x = x
            self._selection_end_idx = self._x_to_index(x, plot_left, plot_width)
            self.update()
            return True
        return False

    def handle_selection_release(self, event, plot_left, plot_width):
        """Handle mouse release for selection zoom. Call from mouseReleaseEvent."""
        if self._selecting and event.button() == Qt.MouseButton.LeftButton:
            self._selecting = False

            # With binning, an index stands for a whole bar of `step` rows: the zone ends
            # after the last bar it touches, not one row into it.
            step = self._get_zoom_snap_step(self._zoom_end - self._zoom_start)
            start_idx = min(self._selection_start_idx, self._selection_end_idx)
            end_idx = min(self._full_length, max(self._selection_start_idx, self._selection_end_idx) + step)

            if end_idx - start_idx >= 2:
                with zoom_camera.camera_zoom(self):
                    self.set_zoom_range(start_idx, end_idx)
                return True

            self.update()
        return False

    def draw_selection_overlay(self, painter, plot_left, margin_top, plot_width, plot_height):
        """Draw the selection rectangle during drag. Call in paintEvent."""
        if not self._selecting:
            return

        x1 = max(plot_left, min(self._selection_start_x, self._selection_end_x))
        x2 = min(plot_left + plot_width, max(self._selection_start_x, self._selection_end_x))

        if x2 > x1:
            # Selection highlight: very transparent fill with a solid border
            selection_rect = QRect(int(x1), int(margin_top), int(x2 - x1), int(plot_height))

            try:
                _acc = QColor(get_theme_colors(self).get("accent", QColor(59, 130, 246)))
            except Exception:
                _acc = QColor(59, 130, 246)
            fill_color = QColor(_acc)
            fill_color.setAlpha(20)
            painter.fillRect(selection_rect, fill_color)

            # Solid blue border (reset brush to avoid filling with previous brush)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            _acc.setAlpha(200)
            pen = QPen(_acc, 1.5)
            painter.setPen(pen)
            painter.drawRect(selection_rect)

