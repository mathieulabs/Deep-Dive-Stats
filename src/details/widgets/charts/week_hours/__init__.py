# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Week by Hour: when you review in the week. A grid of the 7 days of the week by the 24
hours of the day, each cell as dark as the reviews answered then, over the chart's period
and decks.

Days and hours are the clock's (your computer's time zone): a review at 1:00 on Saturday is
in Saturday's row, at 1:00. The data is one grouped query on the review history, read in the
background and kept until the history changes (logic.metrics.review_buckets)."""

import time

from aqt.qt import QColor, QEasingCurve, QFont, QPainter, QPen, QPointF, QRectF, Qt, QVariantAnimation, QWidget

from ...chart_utils.formatting import fmt_num, fmt_num_trim_zeros
from ...chart_utils.theme import get_theme_colors, is_night_mode
from .....i18n import N_, tr, tr_n, weekday_long, weekday_short

WIDGET_TYPE = "week_hours"
LABEL = N_("Week by Hour")

_LEFT_PAD = 6
_TOP_PAD = 4
_GAP = 2  # between the cells


def fetch_counts(cfg, deck_id, is_deleted, days):
    """{(weekday 0 Monday .. 6 Sunday, hour 0-23): reviews} of the period of the day rows."""
    from ....logic.metrics.review_buckets import did_limit, range_from_days, week_hour_counts

    rng = range_from_days(days)
    if not rng:
        return {}
    return week_hour_counts(did_limit(cfg, deck_id, is_deleted), *rng)


class WeekHoursChart(QWidget):
    """The grid. set_source() then set_payload(day rows of the period): the counts are read in
    the background and the cells move to them (each one from its old shade)."""

    def __init__(self, cfg, parent=None, owner=None):
        super().__init__(parent)
        self._cfg = cfg
        self._chart_owner = owner or "deep_dive"
        self._source_args = (None, False)
        self._counts = {}
        self._from = {}  # the counts a transition starts from
        self._t = 1.0  # transition progress
        self._pending_key = None
        self._cache = {}
        self._hover = None
        self._tip = None
        self._shown_once = False  # its cells have filled in once (the intro)
        self.chart_opacity_pct = 100
        self.binning_override = None
        self.setMouseTracking(True)
        self.setMinimumHeight(120)
        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(280)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._anim.valueChanged.connect(self._on_anim)
        # Known to the animation queue as a chart (its place in a refresh's cascade, see
        # animations.chart_policy); the few things the queue reads on a chart.
        self._is_chart_anim_target = True
        self.animation = self._anim
        self._initial_animation_done = False

    # The queue and the export read and set a chart's progress: here, the transition's (an
    # export sets it to 1, the cells then show their final shades).
    @property
    def _progress(self):
        return self._t

    @_progress.setter
    def _progress(self, value):
        self._t = float(value)
        self.update()

    def _has_meaningful_data_for_animation(self):
        return any(self._counts.values())

    def maybe_start_initial_animation(self):
        if not self._shown_once and any(self._counts.values()) and self._animate() and self._appear():
            self._shown_once = True
            self._initial_animation_done = True
            self._from = {}
            self._t = 0.0
            self._anim.stop()
            self._anim.start()

    def _finish_without_animation(self):
        self._anim.stop()
        self._t = 1.0
        self.update()

    # -- what the menus and builders call ---------------------------------------------------

    def apply_options(self, *_args, **_kwargs):
        """(No average line or running total on a grid.)"""

    def set_chart_opacity(self, pct):
        self.chart_opacity_pct = int(pct)
        self.update()

    def set_source(self, cfg, deck_id=None, is_deleted=False):
        self._cfg = cfg or self._cfg
        self._source_args = (deck_id, bool(is_deleted))

    def prefetch(self, days):
        """Read the counts of these days now, without drawing them (see DailyMetricChart):
        True when they are there already."""
        days = list(days or [])
        key = self._key(days)
        if not days or key in self._cache:
            return True
        self._read(days, key, apply=False)
        return False

    def is_ready(self, days):
        days = list(days or [])
        return not days or self._key(days) in self._cache

    def set_payload(self, days):
        """The day rows of the chart's period (the counts are read for their dates)."""
        days = list(days or [])
        if not days and self._counts:
            # No day rows yet (the period not loaded): keep what is shown until they come,
            # rather than emptying the grid for an instant.
            return
        key = self._key(days)
        hit = self._cache.get(key)
        if hit is not None:
            self._set_counts(hit)
            return
        self._read(days, key, apply=True)

    def _read(self, days, key, apply=True):
        if self._pending_key == key:
            if apply:
                self._pending_apply = True
            return
        self._pending_key = key
        self._pending_apply = bool(apply)
        cfg = self._cfg
        deck_id, deleted = self._source_args

        def work():
            return fetch_counts(cfg, deck_id, deleted, days)

        def done(fut):
            try:
                counts = fut.result()
            except Exception:
                from ....logic.logger import log_swallowed

                log_swallowed()
                return
            try:
                if len(self._cache) > 6:
                    self._cache.clear()
                self._cache[key] = counts
                if self._pending_key != key:
                    return  # another deck or period asked since
                self._pending_key = None
                if not getattr(self, "_pending_apply", True):
                    return  # read ahead: the refresh draws it
                self._set_counts(counts)
                from ...common import refresh_parent_chart_header_stats

                refresh_parent_chart_header_stats(self)
            except RuntimeError:
                pass  # closed meanwhile

        from ..common import background_reads

        background_reads.run(id(self), work, done, wait=bool(apply))

    def _key(self, days):
        from aqt import mw

        try:
            stamp = mw.col.db.scalar("SELECT max(id) FROM revlog")
        except Exception:
            stamp = None
        dates = [str(d.get("logical_date") or d.get("date") or "")[:10] for d in days]
        return (self._source_args, (dates[0], dates[-1]) if dates else (), stamp)

    def _set_counts(self, counts):
        counts = dict(counts or {})

        if counts == self._counts:
            return
        # From what the cells show now (the middle of a running transition included).
        self._from = {k: self._share(k) for k in set(self._from) | set(self._counts)}
        first = not self._shown_once and not any(self._counts.values())
        self._counts = counts
        if self._animate() and (self._from or counts):
            self._shown_once = True
            self._intro_at = time.monotonic() if first else 0.0
            self._t = 0.0
            self._anim.stop()
            # In its turn in a refresh's cascade (the old shades stay until then).
            from ....animations.anim_driver import run_in_turn
            from ....animations.chart_policy import chart_animation_queue_plan

            run_in_turn(self, chart_animation_queue_plan(self), self._anim.start, self._anim.duration())
        else:
            # Not shown yet (Anki just opened, a section still hidden): its cells fill in
            # from empty when it shows, as the other charts' bars rise (showEvent).
            if first and counts:
                self._from = {}
            self._t = 1.0
            self.update()
        self._refresh_tip()

    def showEvent(self, event):
        super().showEvent(event)

        if self._shown_once and time.monotonic() - getattr(self, "_intro_at", 0.0) < 1.5 and self._animate() and self._appear():
            # Shown again right after its cells filled in (the main screen fades in the
            # widgets that were loading, right after Anki opens): that first fill was not
            # seen, it plays again now.
            self._intro_at = 0.0
            self._from = {}
            self._t = 0.0
            self._anim.stop()
            self._anim.start()
            return
        if not self._shown_once and any(self._counts.values()) and self._animate() and self._appear():
            self._shown_once = True
            self._intro_at = time.monotonic()
            self._from = {}
            self._t = 0.0
            self._anim.stop()
            self._anim.start()

    def _appear(self):
        try:
            from ....animations.motion import appear_animated

            return appear_animated()
        except Exception:
            return True

    def _animate(self):
        try:
            from ....animations.motion import animations_enabled

            scope = "pinned" if self._chart_owner == "pinned" else "details"
            return self.isVisible() and animations_enabled(scope)
        except Exception:
            return False

    def _on_anim(self, value):
        self._t = float(value)
        self.update()

    def _share(self, key):
        """How strongly a cell is coloured (0: empty cell, else 0.12 to 1) now. Each cell is
        its count against the busiest cell of its own data (square root: a few quiet hours
        still show next to a busy evening; at least 0.12 so any review shows). During a
        transition it moves from what it showed to what it will show, so a period with far
        more reviews does not dim every cell at once, and a cell emptying fades out to the
        end instead of vanishing below some shade."""
        top = max(self._counts.values(), default=0)
        n = float(self._counts.get(key, 0) or 0)
        new = max(0.12, (n / top) ** 0.5) if (top > 0 and n > 0) else 0.0
        if self._t >= 1.0:
            return new
        old = float(self._from.get(key, 0.0) or 0.0)
        return old + (new - old) * self._t

    # -- what it says ------------------------------------------------------------------------

    def total(self):
        return sum(self._counts.values())

    def get_stats_text(self):
        total = self.total()
        if total <= 0:
            return []
        (wd, hour), _n = max(self._counts.items(), key=lambda kv: kv[1])
        days = [sum(self._counts.get((d, h), 0) for h in range(24)) for d in range(7)]
        best = max(range(7), key=lambda d: days[d])
        return [
            tr("Peak: {when}", when=f"{weekday_short(wd)} {hour:02d}:00"),
            tr("Busiest day: {day} ({value}%)", day=weekday_long(best),
               value=fmt_num_trim_zeros(days[best] * 100.0 / total, 0)),
        ]

    def _monday_first(self):
        try:
            from ....ui import Config

            return bool(self._cfg.config.get(Config.HEATMAP_MONDAY_FIRST, False))
        except Exception:
            return True

    def _row_days(self):
        """Weekday (0 Monday) of each row, top to bottom."""
        return list(range(7)) if self._monday_first() else [6, 0, 1, 2, 3, 4, 5]

    # -- drawing -----------------------------------------------------------------------------

    def _geometry(self):
        fm = self.fontMetrics()
        label_w = max(fm.horizontalAdvance(weekday_short(d)) for d in range(7)) + 8
        bottom = fm.height() + 4
        left = _LEFT_PAD + label_w
        w = max(10.0, self.width() - left - _LEFT_PAD)
        h = max(10.0, self.height() - _TOP_PAD - bottom)
        cell_w = w / 24.0
        cell_h = h / 7.0
        return left, _TOP_PAD, cell_w, cell_h

    def _cell_at(self, pos):
        left, top, cw, ch = self._geometry()
        col = int((pos.x() - left) // cw) if pos.x() >= left else -1
        row = int((pos.y() - top) // ch) if pos.y() >= top else -1
        if 0 <= col < 24 and 0 <= row < 7:
            return self._row_days()[row], col
        return None

    def _color(self):
        from ....ui import Config, get_chart_color

        return QColor(get_chart_color(Config.HEATMAP_COLOR, self))

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme = get_theme_colors(self)
        text_col = QColor(theme.get("text_secondary", QColor("#888888")))
        dark = is_night_mode(self)
        base = self._color()
        empty = QColor(255, 255, 255, 14) if dark else QColor(0, 0, 0, 12)
        left, top, cw, ch = self._geometry()
        opacity = max(0.05, min(1.0, self.chart_opacity_pct / 100.0))
        radius = max(1.0, min(cw, ch) * 0.18)
        for row, wd in enumerate(self._row_days()):
            for hour in range(24):
                rect = QRectF(left + hour * cw + _GAP / 2.0, top + row * ch + _GAP / 2.0,
                              max(1.0, cw - _GAP), max(1.0, ch - _GAP))
                share = self._share((wd, hour))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(empty)
                p.drawRoundedRect(rect, radius, radius)
                if share > 0.0:
                    color = QColor(base)
                    color.setAlphaF(min(1.0, share) * opacity)
                    p.setBrush(color)
                    p.drawRoundedRect(rect, radius, radius)
                if self._hover == (wd, hour):
                    outline = QColor(theme.get("text_primary", QColor("#ffffff")))
                    outline.setAlpha(200)
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.setPen(QPen(outline, 1.2))
                    p.drawRoundedRect(rect, radius, radius)
        # Day names on the left, hours under the grid.
        font = QFont(self.font())
        p.setFont(font)
        p.setPen(text_col)
        fm = self.fontMetrics()
        for row, wd in enumerate(self._row_days()):
            if ch < fm.height() * 0.8 and row % 2:
                continue  # too short for every name
            r = QRectF(_LEFT_PAD, top + row * ch, left - _LEFT_PAD - 6, ch)
            p.drawText(r, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), weekday_short(wd))
        step = 3 if cw * 3 >= fm.horizontalAdvance("00") + 6 else 6
        y = top + 7 * ch + 2
        for hour in range(0, 24, step):
            x = left + hour * cw
            p.drawText(QRectF(x - 20, y, cw + 40, fm.height() + 2),
                       int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop), str(hour))
        p.end()

    # -- hover -------------------------------------------------------------------------------

    def mouseMoveEvent(self, event):
        cell = self._cell_at(event.position())
        if cell != self._hover:
            self._hover = cell
            self.update()
        self._refresh_tip(event.position())
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hover = None
        if self._tip is not None:
            self._tip.hide()
        self.update()
        super().leaveEvent(event)

    def hideEvent(self, event):
        if self._tip is not None:
            self._tip.hide()
        super().hideEvent(event)

    def _refresh_tip(self, pos=None):
        if self._hover is None:
            if self._tip is not None:
                self._tip.hide()
            return
        wd, hour = self._hover
        n = int(self._counts.get((wd, hour), 0) or 0)
        total = self.total()
        lines = [
            {"text": f"{weekday_long(wd)}  {hour:02d}:00–{(hour + 1) % 24:02d}:00", "bold": True},
            {"text": tr_n("{count} review", "{count} reviews", n, count=fmt_num(n))},
        ]
        if total > 0:
            lines.append({"text": tr("{value}% of the reviews", value=fmt_num_trim_zeros(n * 100.0 / total, 1))})
        try:
            from ...chart_utils.tooltip import TooltipWindow, show_tooltip_near

            if self._tip is None:
                self._tip = TooltipWindow(self)
            if pos is None:
                pos = self.mapFromGlobal(self.cursor().pos())
            show_tooltip_near(self, self._tip, QPointF(pos).toPoint(), lines=lines)
        except Exception:
            from ....logic.logger import log_swallowed

            log_swallowed()
