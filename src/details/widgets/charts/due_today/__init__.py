# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Due Today by Hour: the learning cards due today (Anki's intraday learning queue), by the
hour they come due, learning and relearning stacked (as Search Stats Extended's Intra Day
Due). Useful with long learning steps or FSRS learning steps within the day.

The data: logic.metrics.future_due.due_today_by_hour (the cards as they are now: no period).
The chart is a stacked chart of the 24 hours of the day (a DailyMetricChart fed with hours)."""

from ..daily_metrics import DailyMetric, DailyMetricChart
from ...chart_utils.formatting import fmt_num
from .....i18n import N_, tr, tr_n


def _series(cfg):
    from ....ui import Config, get_color

    def color(key):
        return get_color(cfg.config, key, "details")

    return [
        {"key": "relearn", "label": tr("Relearning"), "color": color(Config.COLOR_RELEARN), "color_key": Config.COLOR_RELEARN},
        {"key": "learn", "label": tr("Learning"), "color": color(Config.COLOR_LEARN), "color_key": Config.COLOR_LEARN},
    ]


def _rows(payload):
    if isinstance(payload, dict):
        return list(payload.get("rows") or [])
    return list(payload or [])


METRIC = DailyMetric("due_today", N_("Due Today by Hour"), N_("Load and due"), _series, _rows,
                     unit="cards", cumulative=True)


def fetch(cfg, deck_id=None, is_deleted=False):
    from ....logic.metrics.future_due import due_today_by_hour

    return due_today_by_hour(cfg, deck_id, is_deleted)


def has_data(payload):
    return bool(payload and (payload.get("total", 0) or 0) > 0)


class DueTodayChart(DailyMetricChart):
    """The chart; a line marks the current time, and while it is shown it reads the cards
    again each minute (cards come due as time passes, without any review)."""

    def __init__(self, payload, cfg, parent=None, adaptive_binning=True, owner=None):
        payload = dict(payload or {})
        super().__init__(METRIC, payload, cfg, parent=parent, adaptive_binning=adaptive_binning, owner=owner)
        self._payload = payload
        self._source = None
        # Hours, not dates: never zoomed along with the charts of days.
        self._zoom_linked = False
        self._zoom_never = True  # hours of today: never zoomed with the charts of days
        from aqt.qt import QTimer

        self._minute_timer = QTimer(self)
        self._minute_timer.setInterval(60 * 1000)
        self._minute_timer.timeout.connect(self._on_minute)

    @property
    def binning_override(self):
        return False

    @binning_override.setter
    def binning_override(self, _value):
        pass  # always one bar per hour

    def set_source(self, cfg, deck_id=None, is_deleted=False):
        """Where the minute refresh reads the cards (the deck shown)."""
        self._source = (cfg, deck_id, bool(is_deleted))

    def set_payload(self, payload, transition_mode=None):
        self._payload = dict(payload or {})
        self.set_days(self._payload, transition_mode=transition_mode)

    def showEvent(self, event):
        super().showEvent(event)
        self._minute_timer.start()

    def hideEvent(self, event):
        self._minute_timer.stop()
        super().hideEvent(event)

    def _on_minute(self):
        if not self.isVisible() or self._source is None or getattr(self, "_data_transition_active", False):
            return
        try:
            payload = fetch(*self._source)
        except Exception:
            return
        if payload.get("rows") != (self._payload or {}).get("rows") or payload.get("due_now") != self._payload.get("due_now"):
            self.set_payload(payload)
            try:
                from ...common import refresh_parent_chart_header_stats

                refresh_parent_chart_header_stats(self)
            except Exception:
                pass
        else:
            self._payload = payload
            self.update()  # the line of the current time moves

    def paintEvent(self, event):
        super().paintEvent(event)
        self._draw_now_line()

    def _draw_now_line(self):
        """A dashed line at the current time (the day's 24 hours as drawn; not while zoomed)."""
        import time

        geom = getattr(self, "_plot_geom", None)
        start = (self._payload or {}).get("start")
        if not geom or not start or getattr(self, "_is_zoomed", False):
            return
        frac = (time.time() - float(start)) / 86400.0
        if not 0.0 <= frac <= 1.0:
            return
        from aqt.qt import QColor, QPainter, QPen, QPointF, Qt
        from ...chart_utils.theme import get_theme_colors

        left, top, width, height = geom
        x = left + width * frac
        color = QColor(get_theme_colors(self).get("text") or "#888888")
        color.setAlpha(170)
        pen = QPen(color, 1.2)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(pen)
            painter.drawLine(QPointF(x, top), QPointF(x, top + height))
        finally:
            painter.end()

    def get_stats_text(self):
        import time

        p = getattr(self, "_payload", None) or {}
        total = int(p.get("total", 0) or 0)
        if not total:
            return []
        due_now = int(p.get("due_now", 0) or 0)
        later = int(p.get("later", 0) or 0)
        out = [
            tr("Due now: {value}", value=tr_n("{count} card", "{count} cards", due_now, count=fmt_num(due_now))),
            tr("Later today: {value}", value=tr_n("{count} card", "{count} cards", later, count=fmt_num(later))),
        ]
        nxt = p.get("next_due")
        if nxt:
            from datetime import datetime

            at = datetime.fromtimestamp(int(nxt)).strftime("%H:%M")
            mins = max(1, int(round((int(nxt) - time.time()) / 60.0)))
            if mins < 60:
                out.append(tr("Next card in {minutes} min ({time})", minutes=mins, time=at))
            else:
                out.append(tr("Next card in {hours} h {minutes} min ({time})", hours=mins // 60,
                              minutes=mins % 60, time=at))
        return out
