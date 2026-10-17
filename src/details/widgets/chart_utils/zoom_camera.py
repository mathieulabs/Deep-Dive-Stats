# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Zoom animation shared by the time charts (activity, breakdown, retention, added).

A zoom change is applied at once to the data. Inside camera_zoom(), each visible chart
touched by the change is grabbed before it changes and again after, then animated:

- Bar charts zoomed on the same rows: the chart draws itself on a moving window, frame by
  frame (see charts.common.zoom_view), so bars stay sharp and the axis glides.
- Otherwise (retention lines, daily <-> 10-minute data, bars <-> review dots): the two
  images are moved by their time windows while one fades into the other.
"""
import math
import re
from contextlib import contextmanager
from datetime import datetime, timedelta

from aqt.qt import (
    QAbstractScrollArea,
    QApplication,
    QCursor,
    QEasingCurve,
    QEvent,
    QMouseEvent,
    QPainter,
    QPixmap,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QRegion,
    Qt,
    QTimer,
    QVariantAnimation,
    QWidget,
)

from ...animations.motion import animations_enabled
from ...logic.logger import log_swallowed
from .geometry import ChartGeometry
from .theme import palette_memo

DURATION_MS = 280
VECTOR_DURATION_MS = 300
SWITCH_DURATION_MS = 240
SINK_DURATION_MS = 260
SWITCH_AT = 0.7  # share of a running zoom after which a page switch may start
EDGE_BAND = 0.12  # share of the view near each edge where bars count less for the axis
LABEL_OUT = 0.3  # the old labels are gone at this progress; the new ones start at LABEL_IN_AT (short overlap, no blank moment)
LABEL_IN_AT = 0.2
LABEL_FADE = 0.5  # share of the zoom used to fade the old labels out / the new in
MAX_RATIO = 16.0
_EASE = QEasingCurve(QEasingCurve.Type.OutQuad)
_EASE_IN = QEasingCurve(QEasingCurve.Type.InOutQuad)
_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
_PRETTY_YEAR = re.compile(r"^([A-Za-z]{3})[A-Za-z]*\.?\s+(\d{1,2}),\s*(\d{4})$")
_PRETTY_TIME = re.compile(r"^([A-Za-z]{3})[A-Za-z]*\.?\s+(\d{1,2}),\s*(\d{1,2}):(\d{2})$")

_depth = 0
_pending = {}  # id(chart) -> state captured before the change


def _scope(chart):
    try:
        from aqt import mw

        return "pinned" if chart.window() is mw else "details"
    except Exception:
        return "all"


def _parse_label(text, ref_year=None):
    """(start datetime, bin length) for a row label, or None."""
    if isinstance(text, datetime):
        return text, timedelta(days=1)
    s = str(text or "").strip()
    if not s:
        return None
    for fmt, step in (("%Y-%m-%d %H:%M", timedelta(minutes=10)), ("%Y-%m-%d", timedelta(days=1))):
        try:
            return datetime.strptime(s, fmt), step
        except ValueError:
            pass
    m = _PRETTY_YEAR.match(s)
    if m and m.group(1).lower() in _MONTHS:
        try:
            return datetime(int(m.group(3)), _MONTHS.index(m.group(1).lower()) + 1, int(m.group(2))), timedelta(days=1)
        except ValueError:
            return None
    m = _PRETTY_TIME.match(s)
    if m and m.group(1).lower() in _MONTHS:
        month, day = _MONTHS.index(m.group(1).lower()) + 1, int(m.group(2))
        base = int(ref_year or datetime.now().year)
        best = None
        for year in (base - 1, base, base + 1):
            try:
                dt = datetime(year, month, day, int(m.group(3)), int(m.group(4)))
            except ValueError:
                continue
            if best is None or abs((dt - datetime(base, 7, 1)).days) < abs((best - datetime(base, 7, 1)).days):
                best = dt
        return (best, timedelta(minutes=10)) if best else None
    return None


def _row_text(row):
    if isinstance(row, (list, tuple)):
        return row[0] if row else None
    if isinstance(row, dict):
        for k in ("date", "logical_date", "pretty_date", "label", "x"):
            if row.get(k):
                return row.get(k)
    return None


def window_times(chart, ref_year=None):
    """(start, end) in seconds of the rows the chart shows, or None."""
    from .zoom_mixin import zoom_rows

    try:
        rows = zoom_rows(chart)
        s, e = int(chart._zoom_start), int(chart._zoom_end)
        if not (0 <= s < e <= len(rows)):
            return None
        first = _parse_label(_row_text(rows[s]), ref_year)
        last = _parse_label(_row_text(rows[e - 1]), ref_year)
        if not first or not last:
            return None
        t0 = first[0].timestamp()
        t1 = (last[0] + last[1]).timestamp()
        return (t0, t1) if t1 > t0 else None
    except Exception:
        return None


def _plot_x(chart):
    """(left, right) margins of the plot area."""
    try:
        if hasattr(chart, "_get_margins"):
            ml, mr = chart._get_margins()
            return float(ml), float(mr)
        if hasattr(chart, "_get_margin_right"):
            fm = chart.fontMetrics()
            return float(ChartGeometry.calculate_dynamic_left_margin(fm, 100)), float(chart._get_margin_right(fm))
    except Exception:
        log_swallowed()
    return 0.0, 0.0


def _window_of(widget, ref_year=None):
    """Time window (seconds) shown by a chart or by the review dots view."""
    getter = getattr(widget, "zoom_window_seconds", None)
    if callable(getter):
        try:
            return getter()
        except Exception:
            return None
    return window_times(widget, ref_year)


def _snapshot(chart, ref_year=None):
    ml, mr = _plot_x(chart)
    try:
        index = (int(chart._zoom_start), int(chart._zoom_end), int(chart._full_length))
    except (AttributeError, TypeError, ValueError):
        index = None
    return {
        "pixmap": chart.grab(),
        "window": _window_of(chart, ref_year),
        "index": index,
        "rows_id": id(chart._full_data) if hasattr(chart, "_full_data") else None,
        "plot": (ml, mr),
        "size": (chart.width(), chart.height()),
    }


def _in_viewport(widget):
    """False when widget sits in a scroll area but out of what it shows (nothing to animate)."""
    p = widget.parentWidget()
    while p is not None:
        if isinstance(p, QAbstractScrollArea):
            vp = p.viewport()
            if not vp.rect().intersects(QRect(widget.mapTo(vp, QPoint(0, 0)), widget.size())):
                return False
        p = p.parentWidget()
    return True


def _can_animate(widget):
    try:
        return (
            widget.isVisible()
            and widget.width() > 40
            and widget.height() > 40
            and animations_enabled(_scope(widget))
            and _in_viewport(widget)
        )
    except RuntimeError:
        return False


def _rehover(chart):
    """Put the hover marker where the mouse is, as if it had just moved there.

    The marker is kept as a bar index, which points to another day once the zoom changed:
    without this it is drawn in the wrong place until the mouse moves, then jumps. Done
    before the 'after' picture, so the animation already ends on the right marker."""
    try:
        if getattr(chart, "_zoom_camera", None) is not None or not chart.isVisible():
            return
        g = QCursor.pos()
        local = chart.mapFromGlobal(g)
        if not chart.rect().contains(local):
            if getattr(chart, "hover_index", -1) not in (-1, None):
                chart.hover_index = -1  # mouse elsewhere: the old index is meaningless now
            return
        ev = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(local),
            QPointF(g),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            QApplication.keyboardModifiers(),
        )
        QApplication.sendEvent(chart, ev)
    except RuntimeError:
        pass
    except Exception:
        log_swallowed()


def touch(chart):
    """Grab chart before its zoom or data changes (only inside camera_zoom)."""
    if _depth <= 0 or chart is None or id(chart) in _pending:
        return
    try:
        finish(chart)
        if not _can_animate(chart):
            return
        _pending[id(chart)] = (chart, _snapshot(chart))
    except Exception:
        log_swallowed()


@contextmanager
def camera_zoom(*charts):
    """Animate the zoom / data changes made inside the block on the given charts
    (and on any other chart whose zoom changes in it)."""
    global _depth
    _depth += 1
    for c in charts:
        touch(c)
    try:
        yield
    finally:
        _depth -= 1
        if _depth == 0:
            jobs = list(_pending.values())
            _pending.clear()
            for chart, old in jobs:
                _start(chart, old)


def active():
    return _depth > 0


def running(widget):
    return getattr(widget, "_zoom_camera", None) is not None


def finish(widget):
    """Stop a running zoom animation on widget and show it again."""
    ov = getattr(widget, "_zoom_camera", None)
    if ov is not None:
        ov.stop()


def _freeze(chart):
    try:
        if getattr(chart, "_data_transition_active", False) and hasattr(chart, "_clear_data_transition_state"):
            chart._clear_data_transition_state()
        from ..charts.common.zoom import freeze_chart_transition_state

        freeze_chart_transition_state(chart)
    except Exception:
        log_swallowed()


def _vector_capable(chart):
    return (
        hasattr(chart, "_full_data")
        and hasattr(chart, "_compute_display_data")
        and not hasattr(chart, "_full_retention_data")
        and getattr(chart, "chart_type", "bar") == "bar"
    )


def _start(chart, old):
    try:
        if not _can_animate(chart) or (chart.width(), chart.height()) != old["size"]:
            chart.update()
            return
        _freeze(chart)
        _rehover(chart)
        ref_year = None
        if old["window"]:
            ref_year = datetime.fromtimestamp(old["window"][0]).year
        new = _snapshot(chart, ref_year)
        oi, ni = old.get("index"), new.get("index")
        same_rows = old.get("rows_id") is not None and old.get("rows_id") == new.get("rows_id")
        if _vector_capable(chart) and same_rows and oi and ni and oi[2] == ni[2] and oi != ni:
            _VectorZoom(chart, old, new).start()
        else:
            _PixmapZoom(chart, [chart], old, new).start()
    except Exception:
        log_swallowed()
        chart.update()


def _limit_ratio(a, b):
    """Windows used for the image animation. Past MAX_RATIO (e.g. 6 hours to 2 years)
    the smaller window is widened around its middle: the move stays readable and the
    small image is still drawn over the whole widened window, so it starts / ends
    filling the plot."""
    wa, wb = a[1] - a[0], b[1] - b[0]
    if wa <= 0 or wb <= 0:
        return a, b

    def widen(small, big, width):
        mid = (small[0] + small[1]) / 2.0
        s0 = max(big[0], min(mid - width / 2.0, big[1] - width))
        return (s0, s0 + width)

    if wb / wa > MAX_RATIO:
        a = widen(a, b, wb / MAX_RATIO)
    elif wa / wb > MAX_RATIO:
        b = widen(b, a, wa / MAX_RATIO)
    return a, b


def _zoom_path(a, b, e):
    """Window at eased progress e when moving from a to b: a zoom about the point that
    stays still, with a width changing at a constant rate."""
    (a0, a1), (b0, b1) = a, b
    wa, wb = a1 - a0, b1 - b0
    if wa <= 0 or wb <= 0:
        return b0, b1
    if abs(wb - wa) < 1e-6 * max(wa, wb):
        return a0 + (b0 - a0) * e, a1 + (b1 - a1) * e
    w = math.exp(math.log(wa) + (math.log(wb) - math.log(wa)) * e)
    p = (a0 * wb - b0 * wa) / (wb - wa)
    v0 = p - (p - a0) * w / wa
    return v0, v0 + w


def _grab_without_children(widget):
    """widget.grab() without its child widgets (this overlay is one of them)."""
    dpr = widget.devicePixelRatioF() or 1.0
    pm = QPixmap(max(1, int(round(widget.width() * dpr))), max(1, int(round(widget.height() * dpr))))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    widget.render(pm, QPoint(0, 0), QRegion(), QWidget.RenderFlag(0))
    return pm


_NO_PAINT = object()


def _suppress_paint(widget):
    # The chart may already have its own paintEvent on the instance (the idle-frame cache of
    # ChartAnimationMixin): it is kept aside and put back afterwards, not deleted.
    d = widget.__dict__
    if "_zc_saved_paint" not in d:
        d["_zc_saved_paint"] = d.get("paintEvent", _NO_PAINT)
    widget.paintEvent = lambda _e: None


def _restore_paint(widget):
    d = widget.__dict__
    if "_zc_saved_paint" not in d:
        return  # not suppressed (or already given back, e.g. stop() then the overlay's destroyed signal)
    saved = d.pop("_zc_saved_paint")
    if saved is _NO_PAINT:
        d.pop("paintEvent", None)
    else:
        widget.paintEvent = saved


def _release_overlay(state, hidden):
    """What an overlay leaves behind if it is destroyed without stop() (host closed, tab gone)."""
    if state.get("memo"):
        state["memo"] = False
        palette_memo(False)
    for w in hidden:
        try:
            if getattr(w, "_zoom_camera", None) is None:
                _restore_paint(w)
        except RuntimeError:
            pass


class _Overlay(QWidget):
    """Animation drawn over host; the widgets in hidden are not painted meanwhile."""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        pe = cls.__dict__.get("paintEvent")
        if pe is not None:
            def guarded(self, event, _pe=pe):
                # A synchronous repaint() must never start inside a paint of the same widget.
                self._in_paint = True
                try:
                    return _pe(self, event)
                finally:
                    self._in_paint = False
            cls.paintEvent = guarded

    def __init__(self, host, hidden, duration=DURATION_MS):
        super().__init__(host)
        self._in_paint = False
        self._memo_state = {"memo": False}
        self._host = host
        self._hidden = [w for w in hidden if w is not None]
        self._t = 0.0
        self._done_callbacks = []
        self._progress_callbacks = []
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setGeometry(host.rect())
        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(int(duration))
        self._anim.valueChanged.connect(self._on_value)
        self._anim.finished.connect(self.stop)
        _st, _hid = self._memo_state, list(self._hidden)
        self.destroyed.connect(lambda *_a, _st=_st, _hid=_hid: _release_overlay(_st, _hid))

    def on_done(self, callback):
        self._done_callbacks.append(callback)

    def on_progress(self, threshold, callback):
        """callback once the animation reaches threshold (0..1), or when it ends."""
        self._progress_callbacks.append([float(threshold), callback])

    def start(self):
        for w in [self._host] + self._hidden:
            prev = getattr(w, "_zoom_camera", None)
            if prev is not None and prev is not self:
                prev.stop()
            w._zoom_camera = self
        for w in self._hidden:
            _suppress_paint(w)
        if not self._memo_state["memo"]:
            self._memo_state["memo"] = True
            palette_memo(True)
        self._on_value(0.0)
        self.show()
        self.raise_()
        # Start the clock after the synchronous work of this change (other overlays being
        # prepared) so the first frames are not skipped.
        QTimer.singleShot(0, self._begin_clock)

    def _warm(self):
        """Work the first frames would do once (caches); done before the clock starts."""

    def _begin_clock(self):
        try:
            self._warm()
        except Exception:
            log_swallowed()
        try:
            if getattr(self._host, "_zoom_camera", None) is self:
                self._anim.start()
        except RuntimeError:
            pass

    def stop(self):
        try:
            self._anim.stop()
        except RuntimeError:
            pass
        if self._memo_state["memo"]:
            self._memo_state["memo"] = False
            palette_memo(False)
        for w in [self._host] + self._hidden:
            try:
                if getattr(w, "_zoom_camera", None) is self:
                    w._zoom_camera = None
                    if w in self._hidden:
                        _restore_paint(w)
                    w.update()
            except RuntimeError:
                pass
        try:
            if self._t >= 0.9999 and self.isVisible() and not self._in_paint:
                # The last frame (progress 1) is drawn on screen before the overlay goes: it is
                # the chart itself. The clock ends between two ticks, so without this the
                # picture shown last is the previous tick's, up to a few pixels off, and the
                # chart "snaps" into place.
                self.repaint()
        except RuntimeError:
            pass
        try:
            self.hide()
            self.deleteLater()
        except RuntimeError:
            pass
        # The mouse may have moved during the animation.
        _rehover(self._host)
        self._fire_progress(force=True)
        callbacks, self._done_callbacks = self._done_callbacks, []
        for cb in callbacks:
            try:
                cb()
            except Exception:
                log_swallowed()

    def _on_value(self, value):
        self._t = float(value)
        self.update()
        self._fire_progress()

    def _fire_progress(self, force=False):
        due = [cb for cb in self._progress_callbacks if force or self._t >= cb[0]]
        for cb in due:
            self._progress_callbacks.remove(cb)
            try:
                cb[1]()
            except Exception:
                log_swallowed()


class _PixmapZoom(_Overlay):
    """Old and new images moved by their time windows, with a cross-fade."""

    def __init__(self, host, hidden, old, new, duration=DURATION_MS):
        super().__init__(host, hidden, duration=duration)
        self._old = old
        self._new = new
        a, b = old["window"], new["window"]
        if not (a and b):
            # Rows without dates: place the windows by index when the rows are the same.
            ia, ib = old.get("index"), new.get("index")
            if ia and ib and ia[2] == ib[2] and ia[2] > 0:
                a, b = (float(ia[0]), float(ia[1])), (float(ib[0]), float(ib[1]))
            else:
                a = b = None
        self._windows = _limit_ratio(a, b) if (a and b) else None

    def paintEvent(self, _event):
        # The motion ends a little before the clock does, so the last frame shown is the
        # new image exactly (a leftover of 0.1% still moves thin lines by a pixel or two,
        # which shows as a blink when the real chart replaces the overlay).
        e = _EASE.valueForProgress(max(0.0, min(1.0, self._t / 0.93)))
        w, h = float(self.width()), float(self.height())
        old_pm, new_pm = self._old["pixmap"], self._new["pixmap"]
        (oml, omr), (nml, nmr) = self._old["plot"], self._new["plot"]
        ml = oml + (nml - oml) * e
        mr = omr + (nmr - omr) * e
        plot_h = max(1.0, h - ChartGeometry.MARGIN_BOTTOM)
        plot = QRectF(ml, 0.0, max(1.0, w - ml - mr), plot_h)
        view = _zoom_path(self._windows[0], self._windows[1], e) if self._windows else None
        dpr = old_pm.devicePixelRatio() or 1.0
        outside = [
            r
            for r in (QRectF(0, 0, ml, h), QRectF(w - mr, 0, mr, h), QRectF(ml, plot_h, max(0.0, w - ml - mr), h - plot_h))
            if r.width() > 0 and r.height() > 0
        ]

        def layer(pm, pml, pmr, win, alpha, keep_outside=None):
            """One image (labels and plot) at the given opacity, in a transparent pixmap of its own."""
            out = QPixmap(max(1, int(round(w * dpr))), max(1, int(round(h * dpr))))
            out.setDevicePixelRatio(dpr)
            out.fill(Qt.GlobalColor.transparent)
            q = QPainter(out)
            q.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            q.setOpacity(alpha)
            full = QRectF(0, 0, w, h)
            src_full = QRectF(0, 0, pm.width(), pm.height())
            for r in outside:
                q.save()
                q.setClipRect(r)
                q.drawPixmap(full, pm, src_full)
                q.restore()
            pdpr = pm.devicePixelRatio() or 1.0
            src = QRectF(pml * pdpr, 0.0, max(1.0, w - pml - pmr) * pdpr, plot_h * pdpr)
            if view and win:
                v0, v1 = view
                span = max(1e-9, v1 - v0)
                x0 = plot.left() + (win[0] - v0) / span * plot.width()
                x1 = plot.left() + (win[1] - v0) / span * plot.width()
                target = QRectF(x0, 0.0, max(0.5, x1 - x0), plot_h)
            else:
                target = QRectF(plot)
            q.save()
            if keep_outside is not None and win:
                # Where the other picture is not there yet, this one stays whole: fading it
                # everywhere would dim the chart while the other one is still small.
                nv = keep_outside
                nx0 = plot.left() + (nv[0] - v0) / span * plot.width()
                nx1 = plot.left() + (nv[1] - v0) / span * plot.width()
                other = QRectF(nx0, 0.0, max(0.5, nx1 - nx0), plot_h).toAlignedRect()
                inside = QRegion(other).intersected(QRegion(plot.toAlignedRect()))
                rest = QRegion(plot.toAlignedRect()).subtracted(inside)
                q.setClipRegion(rest)
                q.setOpacity(1.0)
                q.drawPixmap(target, pm, src)
                q.setClipRegion(inside)
                q.setOpacity(alpha)
                q.drawPixmap(target, pm, src)
            else:
                q.setClipRect(plot)
                q.drawPixmap(target, pm, src)
            q.restore()
            q.end()
            return out

        # A cross-fade is a sum of the two images, each scaled by its share: drawing one over
        # the other with an opacity lets the background show through in the middle (the chart
        # would dim and flash).
        a = (
            layer(
                old_pm, oml, omr, self._windows[0] if self._windows else None, 1.0 - e,
                keep_outside=self._windows[1] if (self._windows and view) else None,
            )
            if e < 0.999
            else None
        )
        b = layer(new_pm, nml, nmr, self._windows[1] if self._windows else None, e) if e > 0.001 else None
        p = QPainter(self)
        if a is not None and b is not None:
            mix = QPixmap(a.size())
            mix.setDevicePixelRatio(dpr)
            mix.fill(Qt.GlobalColor.transparent)
            m = QPainter(mix)
            m.drawPixmap(0, 0, a)
            m.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            m.drawPixmap(0, 0, b)
            m.end()
            p.drawPixmap(0, 0, mix)
        else:
            p.drawPixmap(0, 0, a if a is not None else b)
        p.end()


def _bin_step(chart, span):
    try:
        if not bool(getattr(chart, "binning_active", False)):
            return 1
        from .binning import get_bin_size

        return max(1, int(get_bin_size(max(1, int(round(span))))))
    except Exception:
        return 1


def _smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def _row_total(chart, row):
    if isinstance(row, (list, tuple)):
        return float(row[1] or 0.0) if len(row) >= 2 else 0.0
    if isinstance(row, dict):
        return float(sum(float(row.get(c["key"], 0) or 0.0) for c in getattr(chart, "series_config", [])))
    try:
        return float(row or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _scale_row(chart, row, f):
    if f == 1.0:
        return row
    if isinstance(row, (list, tuple)) and len(row) >= 2:
        out = list(row)
        out[1] = float(row[1] or 0.0) * f
        return tuple(out) if isinstance(row, tuple) else out
    if isinstance(row, dict):
        out = dict(row)
        for cfg in getattr(chart, "series_config", []):
            k = cfg["key"]
            out[k] = float(row.get(k, 0) or 0.0) * f
        return out
    return row


def _lerp_row(chart, parent, child, w):
    """child row with its values moved from the parent bin's values (w=0) to its own (w=1)."""
    if w >= 1.0 or parent is None:
        return child
    if isinstance(child, (list, tuple)) and len(child) >= 2:
        pv = float(parent[1] or 0.0) if isinstance(parent, (list, tuple)) and len(parent) >= 2 else 0.0
        out = list(child)
        out[1] = pv + (float(child[1] or 0.0) - pv) * w
        return tuple(out) if isinstance(child, tuple) else out
    if isinstance(child, dict) and isinstance(parent, dict):
        out = dict(child)
        for cfg in getattr(chart, "series_config", []):
            k = cfg["key"]
            pv = float(parent.get(k, 0) or 0.0)
            out[k] = pv + (float(child.get(k, 0) or 0.0) - pv) * w
        return out
    return child


class _VectorZoom(_Overlay):
    """Zoom drawn by the chart itself on a moving window, one frame at a time.

    The bars keep the start bin size, then switch once to the end bin size (e.g. 3 months
    to 1 week): each new bar starts at the height of the bar it comes from and moves to
    its own value, so the bars split (or merge) in one go instead of jumping."""

    SPLIT_T0, SPLIT_T1 = 0.04, 0.75  # time range (0..1) over which a zoom in splits the bars
    SPLIT_RATIO = 6.0  # span ratio over which the coarse bars split into the fine ones
    FADE_W = 0.2  # share of the split over which the coarse bars fade into the fine ones
    FINE_BAR_PX = 3.0  # the split happens around the point where the finer bars get this wide

    def __init__(self, chart, old, new):
        super().__init__(chart, [chart], duration=VECTOR_DURATION_MS)
        self._chart = chart
        self._old = old
        self._new = new
        oi, ni = old["index"], new["index"]
        self._a = (float(oi[0]), float(oi[1]))
        self._b = (float(ni[0]), float(ni[1]))
        span_a, span_b = self._a[1] - self._a[0], self._b[1] - self._b[0]
        k_a, k_b = _bin_step(chart, span_a), _bin_step(chart, span_b)
        self._kf, self._kc = min(k_a, k_b), max(k_a, k_b)
        self._k_start, self._k_end = float(k_a), float(k_b)
        # Spans (rows in view) over which the split happens, in log scale.
        small, large = min(span_a, span_b), max(span_a, span_b)
        (oml, omr) = old["plot"]
        plot_w = max(50.0, chart.width() - oml - omr)
        mid = plot_w * self._kf / self.FINE_BAR_PX
        hi = min(large, max(small, mid * 1.8))
        # The split is spread over a wide range of spans (about 2.5 octaves), so on a big
        # zoom the bars do not all split within the first two or three frames.
        lo = min(hi, max(small, hi / self.SPLIT_RATIO))
        if hi <= lo * 1.05:
            lo, hi = small, large
        self._split = (lo, hi)
        self._zoom_in = self._b[0] >= self._a[0] - 1e-6 and self._b[1] <= self._a[1] + 1e-6
        self._frame = None
        self._max = self._avg = None
        ends = []
        for (w0, w1), k, e in ((self._a, k_a, 0.0), (self._b, k_b, 1.0)):
            s0, rows = self._bins(w0, w1, k)
            ends.append(self._targets(s0, k, rows, w0, w1, e))
        self._end_max = (ends[0][0], ends[1][0])
        # Running total (cumulative line) of the start and end windows: its scale glides
        # from one to the other (see charts.common.zoom_view.cumulative_range).
        full = chart._full_data
        n_rows = len(full)

        def window_total(w0, w1):
            i0 = max(0, int(math.floor(w0)))
            i1 = min(n_rows, int(math.ceil(w1)))
            return sum(_row_total(chart, r) for r in full[i0:i1])

        self._cum_ends = (max(1.0, window_total(*self._a)), max(1.0, window_total(*self._b)))
        self._end_ratio = tuple((x[1] / x[0]) if x[0] > 0 else 0.0 for x in ends)

    def _fine_weight(self, span):
        """0: bars at the coarse bin size, 1: at the fine one."""
        if self._kf == self._kc:
            return 1.0
        lo, hi = self._split
        if span <= lo:
            return 1.0
        if span >= hi:
            return 0.0
        x = (math.log(hi) - math.log(span)) / max(1e-9, math.log(hi) - math.log(lo))
        x = max(0.0, min(1.0, x))
        return x * x * (3.0 - 2.0 * x)

    def _binned(self, rows, k):
        c = self._chart
        prev = getattr(c, "_forced_bin_step", None)
        c._forced_bin_step = k
        try:
            return list(c._compute_display_data(rows))
        finally:
            c._forced_bin_step = prev

    def _slice_binned(self, s, e, k):
        """Bins of size k for rows [s, e) (s a multiple of k). The whole data is binned once
        per size and sliced: the same bins as binning the slice itself, at no cost per frame."""
        cache = self.__dict__.setdefault("_binned_all", {})
        allk = cache.get(k)
        if allk is None:
            allk = cache[k] = self._binned(self._chart._full_data, k)
        i0 = s // k
        return allk[i0 : i0 + int(math.ceil((e - s) / float(k)))]

    def _bins(self, v0, v1, k):
        """(first row index, bins at size k) covering [v0, v1)."""
        n = len(self._chart._full_data)
        s = int(math.floor(v0 / k)) * k
        e = min(n, int(math.ceil(v1 / k)) * k)
        if e <= s:
            e = min(n, s + k)
        return s, self._slice_binned(s, e, k)

    def _bar_ratio(self, slot_px):
        from ..charts.common.zoom_view import dense_bar_ratio

        c = self._chart
        if hasattr(c, "series_config"):
            base = min(0.9, max(0.05, float(getattr(c, "_bar_width_ratio", 1.0))))
        else:
            base = 0.9
        return dense_bar_ratio(slot_px, base)

    def _split_rows(self, v0, v1, w, k_glide, plot_w):
        """Fine bars coming out of their coarse parent bar.

        At w=0 the fine bars of a parent share the parent's place and height (they draw
        the parent bar); at w=1 they are at their own place with their own value.
        Values are per row of the bin, times k_glide (see _build_frame).
        Returns (first row, bars, [(x, width)] in fine bins from the first bar)."""
        c = self._chart
        full = c._full_data
        n = len(full)
        kf, kc = self._kf, self._kc
        # While the coarse bars fade into the fine ones (w < FADE_W) the fine bars keep
        # exactly the coarse bars' shape, so no taller ghost of the coarse bar shows above them.
        w = _smooth((w - self.FADE_W) / (1.0 - self.FADE_W))
        s, fine = self._bins(v0, v1, kf)
        sc = int(math.floor(s / kc)) * kc
        ec = min(n, int(math.ceil((s + len(fine) * kf) / kc)) * kc)
        coarse = self._slice_binned(sc, ec, kc)
        fine_slots = max(1e-6, (v1 - v0) / kf)
        slot_px = plot_w / fine_slots
        r_f = self._bar_ratio(slot_px)
        r_c = self._bar_ratio(slot_px * kc / kf)
        groups = {}
        for i in range(len(fine)):
            center = s + i * kf + kf / 2.0
            j = min(len(coarse) - 1, max(0, int((center - sc) // kc))) if coarse else -1
            groups.setdefault(j, []).append(i)
        rows, geom = [None] * len(fine), [None] * len(fine)
        for j, members in groups.items():
            parent = _scale_row(c, coarse[j], k_glide / kc) if j >= 0 else None
            # Parent bar extent, in fine bins from s.
            p0 = (sc + j * kc - s) / float(kf)
            p1 = (min(n, sc + (j + 1) * kc) - s) / float(kf)
            pw = (p1 - p0) * r_c
            left = (p0 + p1) / 2.0 - pw / 2.0
            m = len(members)
            for t, i in enumerate(members):
                rows[i] = _lerp_row(c, parent, _scale_row(c, fine[i], k_glide / kf), w)
                tiled_x, tiled_w = left + t * pw / m, pw / m
                own_x, own_w = i + (1.0 - r_f) / 2.0, r_f
                geom[i] = (tiled_x + (own_x - tiled_x) * w, tiled_w + (own_w - tiled_w) * w)
        return s, rows, geom

    def _targets(self, s, k, rows, v0, v1, e):
        """(axis max, average) of the bars in [v0, v1).

        Bars close to the edges of the view count less, so a tall bar leaving the view
        lowers the axis gradually even when the view moves fast (one day per pixel).
        At the start and end of the animation every bar in view counts fully, as in the
        chart itself."""
        c = self._chart
        n = len(c._full_data)
        span = max(1e-9, v1 - v0)
        band = EDGE_BAND * span
        ends = 1.0 - _smooth(min(e, 1.0 - e) / 0.12)
        active_only = bool(getattr(c, "avg_on_active_days", False))
        mx, wsum, vsum = 0.0, 0.0, 0.0
        for i, row in enumerate(rows):
            b0 = s + i * k
            b1 = min(n, b0 + k)
            if b1 <= b0:
                continue
            frac = (min(b1, v1) - max(b0, v0)) / float(b1 - b0)
            if frac <= 0:
                continue
            frac = min(1.0, frac)
            center = (b0 + b1) / 2.0
            inside = min(center - v0, v1 - center)
            weight = max(_smooth(inside / band) if band > 0 else 1.0, ends)
            if frac < 0.5:
                # A bar only just touching the view (the window is not on the bin grid)
                # does not count fully, or the axis would jump when it enters or leaves.
                weight *= _smooth(frac / 0.5)
            total = _row_total(c, row)
            mx = max(mx, total * weight)
            if total > 0 or not active_only:
                wsum += frac * weight
                vsum += total * frac * weight
        return (mx if mx > 0 else 1.0), (vsum / wsum if wsum > 0 else 0.0)

    def _view_of(self, s, k, v0, v1):
        """(offset, view) in bars of size k for the window [v0, v1), bars starting at row s.
        The chart draws a last, shorter bin (when the row count is not a multiple of k) as a
        full bar, so rows are mapped the same way."""
        n = len(self._chart._full_data)
        full_bins = n // k
        rest = n - full_bins * k

        def slot(row):
            if rest == 0 or row <= full_bins * k:
                return row / float(k)
            return full_bins + (row - full_bins * k) / float(rest)

        return slot(v0) - s / float(k), max(1e-6, slot(v1) - slot(v0))

    def _true_cumulative(self, s, k, count):
        """Running total of the real counts of `count` bins of size k from row s. The bars
        drawn are rescaled (k_glide) so their height stays continuous while the bin size
        changes; the total line must not be: it would overshoot the real total."""
        return self._cumulative_of(s, k, self._slice_binned(s, min(len(self._chart._full_data), s + count * k), k))

    def _cumulative_of(self, s, k, rows):
        """The running total line the chart itself would draw for these bars."""
        c = self._chart
        saved = {a: getattr(c, a, None) for a in ("data", "_zoom_start", "_zoom_end")}
        c.data = rows
        c._zoom_start, c._zoom_end = s, s + len(rows) * k
        c._forced_bin_step = 1
        c._invalidate_data_caches()
        try:
            return list(c._get_cumulative())
        finally:
            for a, v in saved.items():
                setattr(c, a, v)
            c._forced_bin_step = None
            c._invalidate_data_caches()

    def _render(self, s, k, rows, v0, v1, extra=None):
        c = self._chart
        # Before the chart is set up for this frame (_cumulative_of sets and restores it).
        cum_true = self._true_cumulative(s, k, len(rows)) if getattr(c, "cumulative_visible", False) else None
        saved = {a: getattr(c, a, None) for a in ("data", "_zoom_start", "_zoom_end", "hover_index")}
        c.data = rows
        c._zoom_start, c._zoom_end = s, s + len(rows) * k
        c.hover_index = -1
        c._forced_bin_step = 1  # rows are already binned
        e = _EASE.valueForProgress(max(0.0, min(1.0, self._t)))
        (oml, omr), (nml, nmr) = self._old["plot"], self._new["plot"]
        margins = (oml + (nml - oml) * e, omr + (nmr - omr) * e)
        offset, view = self._view_of(s, k, v0, v1)
        c._zoom_view = {
            "offset": offset,
            "view": view,
            "max": self._max,
            # Bar shades follow this steady scale, not the axis: the axis can drop fast when
            # tall bars leave the view, which would flash every bar's colour.
            "color_max": getattr(self, "_glide", None),
            "avg": self._avg,
            "margins": margins,
        }
        if cum_true is not None:
            c._zoom_view["cum_values"] = cum_true
        ta, tb = self._cum_ends
        c._zoom_view["cum_glide"] = (
            math.exp(math.log(ta) + (math.log(tb) - math.log(ta)) * e),
            1.0 - _smooth((e - 0.97) / 0.03),  # weight of the glide: 0 at the end (the chart itself)
        )
        if extra:
            c._zoom_view.update(extra)
        c._zoom_view_plot = None
        c._invalidate_data_caches()
        try:
            # The chart's own drawing (its class paintEvent), not the idle-frame cache.
            c.paintEvent = type(c).paintEvent.__get__(c)
            pm = _grab_without_children(c)
        finally:
            c.paintEvent = lambda _e: None
            for a, v in saved.items():
                setattr(c, a, v)
            c._zoom_view = None
            c._forced_bin_step = None
            c._invalidate_data_caches()
        return pm, getattr(c, "_zoom_view_plot", None)

    def _on_value(self, value):
        self._t = float(value)
        try:
            self._build_frame()
        except Exception:
            log_swallowed()
            self._frame = None
        self.update()
        self._fire_progress()

    RATIO_FOLLOW = True
    CLIP_ALLOWED = 0.95  # the axis may go this far under the tallest bar in view (see _steady_bars)

    def _steady_bars(self, mx, actual, e):
        """Heights of the bars that stay in view move one way only.

        A bar that stays in view is drawn at (its value x k_glide) / axis maximum, and k_glide
        (the bin size the bars glide to) and the axis maximum do not move at the same rate, so
        the bars could first sink and then grow (zooming in; the other way round zooming out).
        Here the factor k_glide / axis is kept between its start and end values and moving only
        towards the end value. The axis never goes under CLIP_ALLOWED of the tallest bar in view.
        The last frame is exactly the chart."""
        ks, ke = self._k_start, self._k_end
        ma, mb = self._end_max
        if abs(ks - ke) < 1e-9 or ma <= 0 or mb <= 0:
            return mx
        kg = math.exp(math.log(ks) + (math.log(ke) - math.log(ks)) * e)
        f0, f1 = ks / ma, ke / mb
        prev = getattr(self, "_f_prev", None)
        if prev is None or self._t < prev[0]:
            prev = (self._t, f0)
        lo, hi = (f0, f1) if f1 >= f0 else (f1, f0)
        if f1 >= f0:
            lo = max(lo, min(prev[1], hi))
        else:
            hi = min(hi, max(prev[1], lo))
        f = min(hi, max(lo, kg / mx))
        steady = max(kg / f, actual * self.CLIP_ALLOWED)
        b = 1.0 - _smooth((e - 0.97) / 0.03)  # at e = 1 the bounds meet the natural value anyway
        out = math.exp(b * math.log(steady) + (1.0 - b) * math.log(mx))
        applied = kg / out
        self._f_prev = (self._t, max(prev[1], applied) if f1 >= f0 else min(prev[1], applied))
        return out

    def _warm(self):
        # The axis maximum of every step of the animation is looked up (and cached) now, so
        # the first frames, which already draw two layers, do not also pay for it.
        for g in range(int(1.0 / self.HOLD_STEP) + 2):
            self._log_target(g)
    HOLD_W = 0.35  # how far back (in animation progress) the axis maximum is averaged
    HOLD_STEP = 0.05

    def _layers(self, v0, v1, e):
        """[(first row, bin size, bins, share, extra)] drawn for the window [v0, v1)."""
        w = self._fine_weight(v1 - v0)
        if self._k_start > self._k_end:
            # Zooming in: the view shrinks fastest at the start, but the bars should not all
            # change shape in the first frames, so the split also follows the time.
            t_eq = 1.0 - (1.0 - min(1.0, e)) ** (1.0 / 2.0)  # time at which the OutQuad ease reaches e
            w = min(w, _smooth((t_eq - self.SPLIT_T0) / (self.SPLIT_T1 - self.SPLIT_T0)))
        # Bars are sums over their bin: a 30-day bar is ~4x a 7-day bar. While zooming,
        # every bar is drawn as (its sum / its bin size) x a bin size gliding from the start
        # one to the end one, so changing the bin size does not change the height scale.
        k_glide = math.exp(math.log(self._k_start) + (math.log(self._k_end) - math.log(self._k_start)) * e)
        layers = []
        if w >= 1.0 or w <= 0.0:
            k = self._kf if w >= 1.0 else self._kc
            s, rows = self._bins(v0, v1, k)
            layers.append((s, k, [_scale_row(self._chart, r, k_glide / k) for r in rows], 1.0, None))
            return layers
        (oml, omr), (nml, nmr) = self._old["plot"], self._new["plot"]
        plot_w = max(10.0, self._chart.width() - (oml + (nml - oml) * e) - (omr + (nmr - omr) * e))
        s, rows, geom = self._split_rows(v0, v1, w, k_glide, plot_w)
        # Right at the start, the coarse bars fade into the fine ones laid on top of
        # them (same shape), so the seams between the fine bars appear softly.
        g = _smooth(w / self.FADE_W)
        if g < 1.0:
            sc, coarse = self._bins(v0, v1, self._kc)
            # The coarse layer keeps its own running total line, so a zoom out ends on the
            # chart's line.
            layers.append((sc, self._kc, [_scale_row(self._chart, r, k_glide / self._kc) for r in coarse], 1.0 - g, None))
        layers.append((s, self._kf, rows, g, {"geom": geom, "radius": 1.8 * w}))
        return layers

    def _targets_of(self, layers, v0, v1, e):
        log_mx, avg = 0.0, 0.0
        for s, k, rows, share, _extra in layers:
            mx_k, avg_k = self._targets(s, k, rows, v0, v1, e)
            log_mx += share * math.log(mx_k)
            avg += share * avg_k
        return log_mx, avg

    def _log_target(self, g):
        """log of the axis maximum the window at progress g * HOLD_STEP calls for (cached)."""
        cache = self.__dict__.setdefault("_hold_cache", {})
        if g in cache:
            return cache[g]
        e = min(1.0, g * self.HOLD_STEP)
        v0, v1 = _zoom_path(self._a, self._b, e)
        n = len(self._chart._full_data)
        v0, v1 = max(0.0, v0), min(float(n), v1)
        val = None
        if v1 - v0 >= 1e-3:
            try:
                val = self._targets_of(self._layers(v0, v1, e), v0, v1, e)[0]
            except Exception:
                log_swallowed()
        cache[g] = val
        return val

    def _build_frame(self):
        e = _EASE.valueForProgress(max(0.0, min(1.0, self._t)))
        v0, v1 = _zoom_path(self._a, self._b, e)
        n = len(self._chart._full_data)
        v0, v1 = max(0.0, v0), min(float(n), v1)
        if v1 - v0 < 1e-3:
            self._frame = None
            return
        layers = self._layers(v0, v1, e)
        log_mx, avg = self._targets_of(layers, v0, v1, e)
        # The axis stays at least on a steady glide from its start value to its end value:
        # a tall bar leaving the view quickly does not rescale everything at once, and on a
        # zoom-out the axis grows ahead of the tall bars coming in.
        ma, mb = self._end_max
        glide = math.exp(math.log(ma) + (math.log(mb) - math.log(ma)) * e)
        # When the view moves fast (a big zoom), tall bars leave it within a frame or two:
        # the axis comes down over the last few frames' average instead of in one step
        # (never below the current target, so no bar is cut), and the averaging fades out
        # towards the end so the last frame is exactly the chart.
        width = self.HOLD_W * (1.0 - _smooth((e - 0.7) / 0.3))
        hold = log_mx
        if width > 1e-3:
            g_hi = int(e / self.HOLD_STEP)
            g_lo = max(0, int(math.ceil((e - width) / self.HOLD_STEP)))
            vals = [self._log_target(g) for g in range(g_lo, g_hi + 1)]
            vals = [v for v in vals if v is not None] + [log_mx]
            hold = max(log_mx, sum(vals) / len(vals))
        mx = max(math.exp(hold), glide)
        # The bars' mean height (average / axis maximum) goes steadily from its start value to
        # its end value. Without this the axis could stay high while the view moves to a quiet
        # part, so the bars first shrink and then grow back.
        r0, r1 = self._end_ratio
        ratio = r0 + (r1 - r0) * e
        if self.RATIO_FOLLOW and ratio > 1e-6 and avg > 0:
            mx = max(math.exp(log_mx), avg / ratio)
        # Zooming in only ever shows bars that were already in view, so the axis never needs
        # to go back up (bars entering the edge weighting could make it wobble).
        prev = getattr(self, "_mx_prev", None)
        if self._zoom_in and prev is not None and self._t >= prev[0]:
            mx = max(min(mx, prev[1]), glide)
        mx = self._steady_bars(mx, math.exp(log_mx), e)
        if not self._zoom_in:
            # Zooming out, the axis follows its glide and only goes above it for a taller bar
            # in view, so the bars do not shrink and grow back at the end.
            mx = min(mx, max(glide, math.exp(log_mx)))
            # Same for the average line: it moves from its start height to its end one with the view.
            if ratio > 1e-6:
                avg = mx * ratio
        self._mx_prev = (self._t, mx)
        self._max = mx
        self._glide = glide
        self._avg = avg
        rendered = [(self._render(s, k, rows, v0, v1, extra), share) for s, k, rows, share, extra in layers]
        if len(rendered) == 1:
            self._frame = rendered[0][0]
            return
        # Mix the two images linearly (no dip in opacity, so no flash).
        (pm_a, plot), share_a = rendered[0]
        (pm_b, _plot_b), share_b = rendered[1]
        mix = QPixmap(pm_a.size())
        mix.setDevicePixelRatio(pm_a.devicePixelRatio())
        mix.fill(Qt.GlobalColor.transparent)
        q = QPainter(mix)
        target = QRectF(0, 0, pm_a.width() / pm_a.devicePixelRatio(), pm_a.height() / pm_a.devicePixelRatio())
        # The first image goes in at its share; the second is scaled by its share in its own
        # pixmap and added at full opacity: Plus together with setOpacity(<1) lowers the alpha
        # (visible flash).
        q.setOpacity(max(0.0, min(1.0, share_a)))
        q.drawPixmap(target, pm_a, QRectF(0, 0, pm_a.width(), pm_a.height()))
        q.setOpacity(1.0)
        part = QPixmap(pm_b.size())
        part.setDevicePixelRatio(pm_b.devicePixelRatio())
        part.fill(Qt.GlobalColor.transparent)
        r = QPainter(part)
        r.setOpacity(max(0.0, min(1.0, share_b)))
        r.drawPixmap(target, pm_b, QRectF(0, 0, pm_b.width(), pm_b.height()))
        r.end()
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        q.drawPixmap(target, part, QRectF(0, 0, part.width(), part.height()))
        q.end()
        self._frame = (mix, plot)

    def paintEvent(self, _event):
        p = QPainter(self)
        w, h = float(self.width()), float(self.height())
        full = QRectF(0, 0, w, h)
        e = _EASE.valueForProgress(max(0.0, min(1.0, self._t)))
        if self._frame is None:
            pm = self._new["pixmap"]
            p.drawPixmap(full, pm, QRectF(0, 0, pm.width(), pm.height()))
            p.end()
            return
        pm, plot = self._frame
        if plot:
            ml, top_y, pw, ph = plot
            bottom = top_y + ph
        else:
            (oml, omr), (nml, nmr) = self._old["plot"], self._new["plot"]
            ml = oml + (nml - oml) * e
            pw = w - ml - (omr + (nmr - omr) * e)
            bottom = h - ChartGeometry.MARGIN_BOTTOM
        plot_rect = QRectF(ml, 0.0, max(1.0, pw), bottom)
        # The plot itself: the frame drawn by the chart.
        p.save()
        p.setClipRect(plot_rect)
        p.drawPixmap(full, pm, QRectF(0, 0, pm.width(), pm.height()))
        p.restore()
        # Axis labels, x labels and stats: the old ones fade out, then the new ones fade
        # in (never both at once, so the texts do not overlap while the bars move).
        t = max(0.0, min(1.0, self._t))
        fade_old = 1.0 - _smooth(t / LABEL_OUT)
        fade_new = _smooth((t - LABEL_IN_AT) / LABEL_OUT)
        outside = (
            QRectF(0, 0, ml, h),
            QRectF(ml + pw, 0, max(0.0, w - ml - pw), h),
            QRectF(ml, bottom, max(0.0, pw), max(0.0, h - bottom)),
        )
        for r in outside:
            if r.width() <= 0 or r.height() <= 0:
                continue
            p.save()
            p.setClipRect(r)
            for src, alpha in ((self._old["pixmap"], fade_old), (self._new["pixmap"], fade_new)):
                if alpha > 0.001:
                    p.setOpacity(alpha)
                    p.drawPixmap(full, src, QRectF(0, 0, src.width(), src.height()))
            p.restore()
        p.end()


class _SinkOut(_Overlay):
    """The old page's picture sinks to the baseline and fades, over the new page."""

    def __init__(self, host, old):
        super().__init__(host, [], duration=SINK_DURATION_MS)
        self._old = old

    def paintEvent(self, _event):
        t = max(0.0, min(1.0, self._t))
        e = _EASE_IN.valueForProgress(t)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w, h = float(self.width()), float(self.height())
        pm = self._old["pixmap"]
        base = h - ChartGeometry.MARGIN_BOTTOM
        ml, mr = self._old["plot"]
        plot = QRectF(ml, 0.0, max(1.0, w - ml - mr), base)
        dpr = pm.devicePixelRatio() or 1.0
        # Axes and labels: fade out quickly.
        p.save()
        p.setOpacity(max(0.0, 1.0 - t * 2.5))
        p.setClipRegion(QRegion(0, 0, int(w), int(h)) - QRegion(plot.toRect()))
        p.drawPixmap(QRectF(0, 0, w, h), pm, QRectF(0, 0, pm.width(), pm.height()))
        p.restore()
        # Bars: squashed toward the baseline while fading.
        p.setOpacity(max(0.0, 1.0 - e))
        height = base * (1.0 - 0.85 * e)
        p.drawPixmap(
            QRectF(plot.left(), base - height, plot.width(), height),
            pm,
            QRectF(plot.left() * dpr, 0.0, plot.width() * dpr, base * dpr),
        )
        p.end()


def switch_stack(stack, index, scope="all"):
    """stack.setCurrentIndex(index) with the zoom animation between the two pages
    (bars <-> one dot per review). Waits for a zoom running on the current page."""
    try:
        if stack.currentIndex() == index and getattr(stack, "_pending_switch", None) is None:
            return
        old_page = stack.currentWidget()
        if old_page is not None and running(old_page) and not running(stack):
            stack._pending_switch = index
            ov = old_page._zoom_camera
            if not getattr(ov, "_switch_hooked", False):
                ov._switch_hooked = True

                def later(stack=stack, scope=scope, page=old_page):
                    target = getattr(stack, "_pending_switch", None)
                    stack._pending_switch = None
                    if target is not None:
                        # The zoom is in its last, nearly still part: end it and go on
                        # with the switch, so there is no pause between the two.
                        finish(page)
                        switch_stack(stack, target, scope)

                ov.on_progress(SWITCH_AT, later)
            return
        stack._pending_switch = None
        if stack.currentIndex() == index:
            return
        finish(stack)
        if old_page is None or not stack.isVisible() or stack.width() < 40 or not animations_enabled(scope):
            stack.setCurrentIndex(index)
            return
        old = _snapshot(old_page)
        ref_year = datetime.fromtimestamp(old["window"][0]).year if old["window"] else None
        stack.setCurrentIndex(index)
        new_page = stack.currentWidget()
        new_window = _window_of(new_page, ref_year)
        same_window = (
            old["window"] and new_window
            and abs(old["window"][0] - new_window[0]) + abs(old["window"][1] - new_window[1])
            < 0.02 * (new_window[1] - new_window[0])
        )
        if same_window and callable(getattr(new_page, "finish_intro", None)):
            # Bars -> review dots over the same hours: the bars sink and fade while the
            # dots pop in (their own intro), instead of a cross-fade of two pictures.
            _SinkOut(stack, old).start()
            return
        finish_intro = getattr(new_page, "finish_intro", None)
        if callable(finish_intro):
            finish_intro()
        _freeze(new_page)
        new = _snapshot(new_page, ref_year)
        _PixmapZoom(stack, [new_page], old, new, duration=SWITCH_DURATION_MS).start()
    except Exception:
        log_swallowed()
        try:
            stack.setCurrentIndex(index)
        except RuntimeError:
            pass


def with_camera(fn):
    """fn with its zoom / data changes animated (see camera_zoom).

    Extra positional arguments (e.g. the "checked" flag of clicked) are dropped when fn
    does not take them, as Qt does for a plain slot."""
    import functools
    import inspect

    try:
        params = inspect.signature(fn).parameters.values()
        max_args = None if any(p.kind is p.VAR_POSITIONAL for p in params) else sum(
            1 for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
        )
    except (TypeError, ValueError):
        max_args = None

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if max_args is not None:
            args = args[:max_args]
        with camera_zoom():
            return fn(*args, **kwargs)

    return wrapper
