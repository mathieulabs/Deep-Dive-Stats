# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The widget gallery, opened by the "+" of the main screen and by "Add Widget..." of the
right-click menu.

Every chart, stat card and the text widget, each shown as it will look, with the user's own
data. The categories are listed on the left (a click scrolls to one, the list follows the
scrolling); at the bottom, a search field looks through everything and a line says where
the new widget goes. A widget already on the main screen has a check mark. One click
adds a widget.

The previews are pictures of real pinned widgets as they will be added (the deck shown, the
period a new widget opens on): each is built by the same factory at a normal widget size out
of sight, then drawn once its data is there and shrunk into its tile (a widget cannot be
shown smaller than it is laid out). A few are built at a time, those in view first, and the
pictures are kept for the next opening while the data stays the same."""

import time

from aqt import mw
from aqt.qt import (
    QApplication, QBrush, QColor, QDialog, QEvent, QFont, QFontMetrics, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLinearGradient, QLineEdit, QObject, QPainter, QPainterPath, QPen, QPixmap, QPointF, QPushButton, QRectF,
    QPoint, QRegion, QScrollArea, QSize, Qt, QTimer, QVBoxLayout, QWidget,
)

from ..imports import Config, ThemeContext, get_theme_colors
from .add_widget_menu import STAT_GROUPS, Choice, chart_groups, default_span
from ... import WidgetRegistry
from ....stats_cards.logic.model import get_stat_card_default_title, get_stat_card_name
from ....stats_cards.ui.style import CARD_CORNER_RADIUS_PX
from .....logic.logger import log_debug, log_swallowed
from ......qss import set_qss
from ......i18n import N_, tr, tr_n, tr_name, upper

# Shown size of a preview, and the size the widget is built at before it is shrunk.
_CHART_PIC = (236, 148)
_CHART_BUILD = (440, 276)
_STAT_PIC = (172, 80)
_STAT_BUILD = _STAT_PIC  # built at the size shown: a shrunk card's text is blurred
_TEXT_PIC = (236, 80)
_COLUMNS = {"chart": 3, "stat": 4, "text": 3}
_NAME_GAP = 6
_SPACING = 14
_RADIUS = 6
_AT_ONCE = 3        # previews built at the same time
_WAIT_MAX = 2.5     # s: a preview whose data takes longer is drawn as it is
_SIDEBAR_W = 168
_CACHE_S = 600      # s: a preview picture is kept this long for the next opening

# (widget type, stat key, size, (deck id, collection change)): (picture, made at).
_pictures = {}
# "Not added" chosen last time (kept while Anki runs, for the next opening).
_only_missing = {"on": False}

_WHERE = {
    None: N_("At the end"),
    "after": N_("After the right-clicked widget"),
    "end": N_("At the end of the line"),
    "newline": N_("On a new line"),
    "newbox": N_("In a new box"),
}


def _colors():
    t = get_theme_colors(ThemeContext.PINNED)
    dark = bool(t.get("is_dark", True))
    accent = QColor(t.get("accent") or "#3b82f6")
    if not accent.isValid():
        accent = QColor("#3b82f6")
    text = QColor(236, 236, 240) if dark else QColor(28, 30, 36)
    muted = QColor(text)
    muted.setAlpha(150)
    return {
        "accent": accent,
        "text": text,
        "muted": muted,
        "card": QColor(255, 255, 255, 10) if dark else QColor(0, 0, 0, 7),
        "hover": QColor(255, 255, 255, 18) if dark else QColor(0, 0, 0, 12),
        "line": QColor(255, 255, 255, 40) if dark else QColor(0, 0, 0, 40),
        "accent_soft": QColor(accent.red(), accent.green(), accent.blue(), 70 if dark else 50),
    }


def _rgba(c):
    return f"rgba({c.red()},{c.green()},{c.blue()},{c.alpha()})"


class _NavButton(QPushButton):
    """A category in the list on the left: its name, how many widgets it shows on the right;
    the one at the top of the view on a light background."""

    def __init__(self, gallery, title):
        super().__init__(title)
        self.gallery = gallery
        self.title = title
        self.count = 0
        self.setFixedHeight(28)

    def set_count(self, n):
        if n != self.count:
            self.count = n
            self.update()

    def paintEvent(self, _event):
        c = self.gallery.colors
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            r = QRectF(self.rect())
            if self.isChecked() or self.underMouse():
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(c["hover"] if self.isChecked() else c["card"])
                p.drawRoundedRect(r, 6, 6)
            enabled = self.isEnabled()
            fm = QFontMetrics(self.font())
            count = str(self.count) if enabled else ""
            count_w = fm.horizontalAdvance(count) if count else 0
            text_c = QColor(c["text"]) if enabled else QColor(c["line"])
            if not self.isChecked() and enabled:
                text_c.setAlpha(215)
            f = QFont(self.font())
            if self.isChecked():
                f.setWeight(QFont.Weight.DemiBold)
            p.setFont(f)
            p.setPen(text_c)
            name = QFontMetrics(f).elidedText(self.title, Qt.TextElideMode.ElideRight, int(r.width() - 26 - count_w))
            p.drawText(r.adjusted(12, 0, -10, 0), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), name)
            if count:
                p.setFont(self.font())
                p.setPen(c["muted"])
                p.drawText(r.adjusted(0, 0, -10, 0), int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), count)
        finally:
            p.end()


class _Tile(QWidget):
    """A preview, its name under it (stat cards show theirs in the picture), a check mark
    when it is on the main screen already (with how many, from 2). On the main screen's
    gallery a click adds one more, and the "−" in the corner (on hover) takes one off.
    Drawn by hand: one widget."""

    def __init__(self, gallery, parent, choice, name, pic_size, search_text, show_name=True, pinned=False,
                 count=None):
        super().__init__(parent)  # in its grid from the start: a widget shown without a parent is a window
        self.gallery = gallery
        self.choice = choice
        self.name = name
        self.pic_size = pic_size
        self.search_text = search_text.lower()
        self.pinned = pinned
        # How many are on the main screen (its gallery); the Deep Dive manager only marks.
        self.count = int(count) if count is not None else (1 if pinned else 0)
        self._show_name = show_name
        self._pixmap = None
        self._text = None
        self._hover = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_tip()
        name_h = QFontMetrics(self.font()).height() + _NAME_GAP if show_name else 0
        self.setFixedSize(pic_size[0], pic_size[1] + name_h)

    def pic_rect(self):
        return QRectF(0, 0, self.pic_size[0], self.pic_size[1])

    def refresh_tip(self):
        if self.gallery.toggle:
            action = (tr("Shown in Deep Dive: click to remove it") if self.pinned
                      else tr("Click to add it to Deep Dive"))
        else:
            action = (tr("Click to add another. − removes one.") if self.count
                      else tr("Click to add it"))
        # What the chart shows (widgets.common.chart_help), then what a click does.
        from ....common.chart_help import help_text

        about = help_text(getattr(self.choice, "widget_type", None)) if getattr(self.choice, "stat_key", None) is None else ""
        if about:
            import html

            tip = f"<p>{html.escape(about)}</p>" + (f"<p><i>{html.escape(action)}</i></p>" if action else "")
        else:
            tip = action
        self.setToolTip(tip)

    def set_pinned(self, on):
        self.pinned = bool(on)
        self.refresh_tip()
        self.update()

    def set_count(self, n):
        self.count = max(0, int(n))
        self.set_pinned(self.count > 0)

    def minus_rect(self):
        """The "−" that takes one off (main screen's gallery, on hover), or None."""
        if self.gallery.toggle or self.count <= 0:
            return None
        r = 8.0
        pic = self.pic_rect()
        return QRectF(pic.left() + 6, pic.top() + 6, 2 * r, 2 * r)

    def put_picture(self, pixmap):
        self._pixmap = pixmap
        self.update()

    def put_text(self, text):
        self._text = text
        self.update()

    def set_hover(self, on):
        self._hover = bool(on)
        self.update()

    def enterEvent(self, event):
        self.set_hover(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.set_hover(False)
        super().leaveEvent(event)

    def _paint_skeleton(self, p, pic, clip, c):
        """The tile while its preview is built: a plain grey block with a light sweeping
        across it (the usual "loading" look of a list of posts)."""
        base = QColor(c["text"])
        base.setAlpha(22)
        shine = QColor(c["text"])
        shine.setAlpha(46)
        sweep = pic.width() * 1.6
        x = pic.left() - pic.width() * 0.3 + sweep * self.gallery.shimmer
        grad = QLinearGradient(QPointF(x - 60, 0), QPointF(x + 60, 0))
        grad.setColorAt(0.0, base)
        grad.setColorAt(0.5, shine)
        grad.setColorAt(1.0, base)
        p.save()
        p.setClipPath(clip)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawPath(clip)
        p.restore()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            minus = self.minus_rect()
            if minus is not None and minus.adjusted(-3, -3, 3, 3).contains(QPointF(event.pos())):
                self.gallery.remove_one(self)
                return
            self.gallery.pick(self.choice, self)
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, _event):
        c = self.gallery.colors
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            pic = self.pic_rect()
            # A stat card's picture has the card's own round corners: follow them.
            radius = CARD_CORNER_RADIUS_PX if self.choice.family == "stat" else _RADIUS
            clip = QPainterPath()
            clip.addRoundedRect(pic, radius, radius)
            if self._pixmap is None or self.choice.family != "stat":
                # Charts and the text get a plain frame; a stat card is a card itself.
                p.fillPath(clip, c["card"])
                p.setPen(QPen(c["line"], 1))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(pic.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
            if self._pixmap is not None and not self._pixmap.isNull():
                p.save()
                p.setClipPath(clip)
                dpr = self._pixmap.devicePixelRatio() or 1.0
                w, h = self._pixmap.width() / dpr, self._pixmap.height() / dpr
                p.drawPixmap(QRectF(pic.center().x() - w / 2, pic.center().y() - h / 2, w, h),
                             self._pixmap, QRectF(self._pixmap.rect()))
                p.restore()
            elif self._text:
                f = QFont(self.font())
                f.setWeight(QFont.Weight.DemiBold)
                p.setFont(f)
                p.setPen(c["text"])
                p.drawText(pic.adjusted(14, 8, -14, -8),
                           int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap), self._text)
            else:
                self._paint_skeleton(p, pic, clip, c)
            if self._hover:
                p.setPen(QPen(c["accent"], 1.5))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(pic.adjusted(0.75, 0.75, -0.75, -0.75), radius, radius)
            if self.gallery.toggle and not self.pinned:
                # Managing Deep Dive: an empty box on the ones not shown, a check on the others.
                r = 7.0
                center = QPointF(pic.right() - r - 6, pic.top() + r + 6)
                p.setPen(QPen(QColor(255, 255, 255, 170), 1.2))
                p.setBrush(QColor(0, 0, 0, 60))
                p.drawEllipse(center, r, r)
            if self.pinned and not self.gallery.toggle and self.count >= 2:
                # How many on the main screen.
                r = 8.0
                center = QPointF(pic.right() - r - 6, pic.top() + r + 6)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(0, 0, 0, 120))
                p.drawEllipse(center, r, r)
                f = QFont(self.font())
                f.setPixelSize(10)
                f.setWeight(QFont.Weight.Bold)
                p.setFont(f)
                p.setPen(QColor(255, 255, 255))
                p.drawText(QRectF(center.x() - r, center.y() - r, 2 * r, 2 * r),
                           int(Qt.AlignmentFlag.AlignCenter), str(self.count) if self.count < 100 else "99+")
            elif self.pinned:
                r = 7.0
                center = QPointF(pic.right() - r - 6, pic.top() + r + 6)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(c["accent"] if self.gallery.toggle else QColor(0, 0, 0, 120))
                p.drawEllipse(center, r, r)
                pen = QPen(QColor(255, 255, 255), 1.6)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(pen)
                p.drawPolyline([QPointF(center.x() - 3.2, center.y() + 0.2),
                                QPointF(center.x() - 0.8, center.y() + 2.6),
                                QPointF(center.x() + 3.4, center.y() - 2.4)])
            minus = self.minus_rect() if self._hover else None
            if minus is not None:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(0, 0, 0, 150))
                p.drawEllipse(minus)
                pen = QPen(QColor(255, 255, 255), 1.8)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                cy = minus.center().y()
                p.drawLine(QPointF(minus.left() + 4.5, cy), QPointF(minus.right() - 4.5, cy))
            if self._show_name:
                p.setFont(self.font())
                name_c = QColor(c["text"])
                if not self._hover:
                    name_c.setAlpha(205)
                p.setPen(name_c)
                fm = p.fontMetrics()
                text = fm.elidedText(self.name, Qt.TextElideMode.ElideRight, int(pic.width()))
                p.drawText(QRectF(0, pic.bottom() + _NAME_GAP, pic.width(), fm.height()),
                           int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop), text)
        finally:
            p.end()


class _WindowGuard(QObject):
    """While the gallery is open: a popup of a preview that still shows (a floating label
    of a chart...) is hidden at once, and named in the log."""

    def __init__(self, gallery):
        super().__init__(gallery)
        self._seen = set()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Show and isinstance(obj, QWidget):
            try:
                from ....chart_utils.tooltip import built_offscreen

                if obj.isWindow() and built_offscreen(obj):
                    obj.hide()
                    name = type(obj).__name__
                    if name not in self._seen:
                        self._seen.add(name)
                        log_debug(f"gallery: hid a preview popup ({name})", tag="PINNED")
            except RuntimeError:
                pass
        return False


class WidgetGallery(QDialog):
    def __init__(self, manager, parent=None, family=None, where=None, only=None, taken=None,
                 stats=None, stats_taken=None, toggle=False, on_toggle=None, on_add=None, on_remove=None,
                 on_reset=None):
        super().__init__(parent or mw)
        self.manager = manager
        # only: the chart types offered, no stat card or text then unless stats (the stat
        # card keys offered) is given too. taken / stats_taken: the ones marked as already
        # there (default: the pinned ones). toggle: a click marks or unmarks a widget and
        # on_toggle(choice, marked) applies it at once; Cancel is for the caller to undo it
        # all (Deep Dive manages its charts and stat cards so).
        self._only = set(only) if only is not None else None
        self._taken = set(taken) if taken is not None else None
        self._stats = set(stats) if stats is not None else None
        self._stats_taken = set(stats_taken) if stats_taken is not None else None
        self.toggle = bool(toggle)
        self._on_toggle = on_toggle
        # on_add(choice) -> id: a click adds the widget at once and the gallery stays open, to
        # add several in a row; a second click on it takes it off again (on_remove(id)). Done
        # keeps them, Cancel is for the caller to undo them all (as Deep Dive's gallery).
        # Without on_add, a click closes it on that widget.
        self._on_add = on_add
        self._on_remove = on_remove
        # on_reset() -> (chart types, stat card keys) shown after putting the defaults back
        # (Deep Dive's manager: "Reset to Default"; Cancel undoes it as the rest).
        self._on_reset = on_reset
        self._added = {}  # tile: [ids of the widgets it added, last one last]
        self._family = family  # where it opens: its previews are built first
        # The period and decks the widgets are added with (and their previews drawn with):
        # None, each widget's own default (a chart: the past month; a stat card: Total) and
        # the current deck.
        self.span = None  # (time_span, custom_days)
        self.deck_ids = None
        self.choice = None
        self.colors = _colors()
        self._queue = []
        self._building = []  # (tile, widget, started at)
        self._sections = []  # (key, family, header, grid widget, grid, tiles)
        self._nav = {}       # section key: sidebar button
        if self.toggle:
            self.setWindowTitle(tr("Charts and Stat Cards"))
        else:
            self.setWindowTitle(tr("Add Chart") if only is not None else tr("Add Widget"))
        self.setProperty("deepdivestats_theme_context", "pinned")
        self.setProperty("deepdivestats_ignore_forced_dark_theme", True)
        try:
            from ....chart_utils.theme import settings_dialog_qss_for

            set_qss(self, settings_dialog_qss_for(ThemeContext.PINNED, default=ThemeContext.PINNED) + self._qss())
        except Exception:
            log_swallowed()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 16)
        outer.setSpacing(14)

        # Top: the title and where the widget goes, the filter and the search on the right.
        top = QHBoxLayout()
        top.setSpacing(10)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel(self.windowTitle())
        title.setObjectName("dd_gallery_title")
        titles.addWidget(title)
        if self.toggle:
            where_text = ""  # the check marks say it
        else:
            where_text = tr_name(_WHERE.get(where, _WHERE[None]))
        self._where_label = QLabel(where_text)
        self._where_label.setObjectName("dd_gallery_sub")
        titles.addWidget(self._where_label)
        self._where_label.setVisible(bool(where_text))
        top.addLayout(titles, 1)

        self._missing_btns = []
        seg = QWidget()
        seg.setObjectName("dd_gallery_seg")
        seg_lay = QHBoxLayout(seg)
        seg_lay.setContentsMargins(2, 2, 2, 2)
        seg_lay.setSpacing(2)
        for label, value in ((tr("All"), False), (tr("Not shown") if self.toggle else tr("Not added"), True)):
            b = QPushButton(label)
            b.setObjectName("dd_gallery_seg_btn")
            b.setCheckable(True)
            b.setAutoDefault(False)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setChecked(bool(_only_missing["on"]) == value)
            b.clicked.connect(lambda _c=False, v=value: self._set_only_missing(v))
            seg_lay.addWidget(b)
            self._missing_btns.append((b, value))
        top.addWidget(seg, 0, Qt.AlignmentFlag.AlignVCenter)

        self.search = QLineEdit(self)
        self.search.setObjectName("dd_gallery_search")
        self.search.setPlaceholderText(tr("Search widgets..."))
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(200)
        self.search.textChanged.connect(self._filter)
        self.search.returnPressed.connect(self._add_first)
        try:
            from .....ui.theme.icons import get_svg_icon
            from aqt.qt import QLineEdit as _QLE

            self.search.addAction(get_svg_icon("search", size=14, context_ref=self), _QLE.ActionPosition.LeadingPosition)
        except Exception:
            log_swallowed()
        top.addWidget(self.search, 0, Qt.AlignmentFlag.AlignVCenter)
        outer.addLayout(top)

        main = QHBoxLayout()
        main.setSpacing(18)
        self._side = QVBoxLayout()
        self._side.setContentsMargins(0, 2, 0, 0)
        self._side.setSpacing(1)
        side_w = QWidget()
        side_w.setObjectName("dd_gallery_side")
        side_w.setFixedWidth(_SIDEBAR_W)
        side_w.setLayout(self._side)
        main.addWidget(side_w)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("dd_gallery_body")
        self._body_lay = QVBoxLayout(body)
        self._body_lay.setContentsMargins(0, 0, 10, 0)
        self._body_lay.setSpacing(8)
        scroll.setWidget(body)
        scroll.verticalScrollBar().valueChanged.connect(self._follow_scroll)
        self._scroll = scroll
        main.addWidget(scroll, 1)
        outer.addLayout(main, 1)

        foot = QHBoxLayout()
        foot.setSpacing(8)
        if not self.toggle:
            self._build_add_options(foot)
        elif self._on_reset is not None:
            reset = QPushButton(tr("Reset to Default"))
            reset.setAutoDefault(False)
            reset.setToolTip(tr("The default charts and stat cards, in their default order and size."))
            reset.clicked.connect(self._reset)
            foot.addWidget(reset)
        foot.addStretch(1)
        cancel = QPushButton(tr("Cancel"))
        cancel.setAutoDefault(False)  # Enter adds the first widget found (see _add_first)
        cancel.clicked.connect(self.reject)
        foot.addWidget(cancel)
        if self.toggle or self._on_add is not None:
            done = QPushButton(tr("Done"))
            done.setAutoDefault(False)
            done.clicked.connect(self.accept)
            foot.addWidget(done)
        outer.addLayout(foot)

        self._build()
        self._side.addStretch(1)
        self._empty = QLabel(tr("No widget found."))
        self._empty.setObjectName("dd_gallery_sub")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._body_lay.addWidget(self._empty)
        self._body_lay.addStretch(1)
        # Room under the last category, so that each one can come to the top of the view
        # (the list on the left marks the one at the top). Sized in _fit_tail_room.
        self._tail = QWidget()
        self._tail.setFixedHeight(0)
        self._body_lay.addWidget(self._tail)

        cols = _COLUMNS["chart"]
        grid_w = cols * _CHART_PIC[0] + (cols - 1) * _SPACING
        bar = self.style().pixelMetric(self.style().PixelMetric.PM_ScrollBarExtent)
        self.setFixedWidth(40 + _SIDEBAR_W + 18 + grid_w + 10 + bar + 4)
        self.resize(self.width(), 680)

        # Where the previews are built: inside the window, out of its visible area. Their
        # popups stay hidden (see chart_utils.tooltip.built_offscreen and _WindowGuard).
        self._stage = QWidget(self)
        self._stage.setProperty("dd_offscreen", True)
        self._stage.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._stage.setGeometry(-6000, -6000, _CHART_BUILD[0], _CHART_BUILD[1] * _AT_ONCE)
        self._guard = _WindowGuard(self)
        QApplication.instance().installEventFilter(self._guard)
        self._timer = QTimer(self)
        self._timer.setInterval(120)
        self._timer.timeout.connect(self._tick)
        # The light sweeping across the tiles still waiting for their preview (0 to 1).
        self.shimmer = 0.0
        self._shimmer_timer = QTimer(self)
        self._shimmer_timer.setInterval(40)
        self._shimmer_timer.timeout.connect(self._shimmer_step)
        self._filter()
        if family:
            QTimer.singleShot(60, lambda f=family: self.go_to(f))

    # -- period and decks of the widgets added ----------------------------------------------

    def _build_add_options(self, row):
        """"Added with: [period] [decks]" (pinned gallery): the widgets clicked are added with
        them, and their previews are drawn with them."""
        lbl = QLabel(tr("Added with:"))
        lbl.setObjectName("dd_gallery_sub")
        row.addWidget(lbl)
        self._span_btn = QPushButton()
        self._span_btn.setAutoDefault(False)
        self._span_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._span_btn.setToolTip(tr("The period of the widgets added from here (a widget without a period keeps none)."))
        self._span_btn.clicked.connect(self._open_span_menu)
        row.addWidget(self._span_btn)
        self._deck_btn = QPushButton()
        self._deck_btn.setAutoDefault(False)
        self._deck_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._deck_btn.setToolTip(tr("The decks of the widgets added from here. By default they follow the deck shown."))
        self._deck_btn.clicked.connect(self._pick_decks)
        row.addWidget(self._deck_btn)
        self._sync_add_options()

    def _sync_add_options(self):
        if getattr(self, "_span_btn", None) is None:
            return
        if self.span is None:
            span_name = tr("Default Period")
        else:
            span_name = ""
            try:
                from .card_chips import span_text

                span_name = span_text(self.manager, {"type": "activity", "time_span": self.span[0],
                                                     "custom_days": self.span[1]})
            except Exception:
                log_swallowed()
            span_name = span_name or tr("Custom")
        from ....common.menu_chevron import attach_chevron, place_chevron, with_room

        for btn, text in ((self._span_btn, span_name), (self._deck_btn, self._deck_name())):
            btn.setText(with_room(text))
            attach_chevron(btn)
            place_chevron(btn)

    def _deck_name(self):
        ids = list(self.deck_ids or [])
        if not ids:
            return tr("Current Deck")
        if ids == ["deleted"]:
            return tr_name(N_("Deleted Cards"))
        if len(ids) == 1:
            try:
                return mw.col.decks.name(int(ids[0])).split("::")[-1]
            except Exception:
                log_swallowed()
        return tr_n("{n} deck", "{n} decks", len(ids))

    def _open_span_menu(self):
        try:
            from .card_chips import themed_menu
            from .....ui.shared.span_menu import populate_span_menu

            menu = themed_menu(self, self.manager)
            auto = menu.addAction(tr("Default Period"))
            auto.setCheckable(True)
            auto.setChecked(self.span is None)
            auto.setToolTip(tr("Charts: the past month. Stat cards: Total."))
            auto.triggered.connect(lambda _=False: self._set_span(None))
            menu.addSeparator()
            # (no period checked in the list while it is the default one: -999 is none of them)
            current = self.span or (-999, None)
            populate_span_menu(
                menu, current[0], current[1],
                lambda v, d=None: self._set_span((v, d)),
                self.manager._config_manager,
            )
            menu.exec(self._span_btn.mapToGlobal(self._span_btn.rect().bottomLeft()))
        except Exception:
            log_swallowed()

    def _set_span(self, span):
        if span is not None:
            try:
                span = (int(span[0]), span[1])
            except (TypeError, ValueError):
                return
        if span == self.span:
            return
        self.span = span
        self._sync_add_options()
        self._redo_previews()

    def _pick_decks(self):
        try:
            from ... import DeckMultiSelectDialog

            dialog = DeckMultiSelectDialog(self.deck_ids, parent=self)
            if not dialog.exec():
                return
            ids = dialog.selected_deck_ids or None
        except Exception:
            log_swallowed()
            return
        if ids == self.deck_ids:
            return
        self.deck_ids = ids
        self._sync_add_options()
        self._redo_previews()

    def view_key(self):
        """What the previews depend on besides the widget: its period and decks."""
        return (self.span, tuple(self.deck_ids) if self.deck_ids else None)

    def fields_for(self, choice):
        """(time_span or None for the default, custom_days, deck_ids) a widget is added with."""
        from .card_chips import has_time_span

        span, days = self.span if self.span is not None else (None, None)
        if span is not None and not has_time_span({"type": choice.widget_type, "stat_key": choice.stat_key}):
            span, days = None, None
        return span, days, (list(self.deck_ids) if self.deck_ids else None)

    def _redo_previews(self):
        """Every preview drawn again with the new period or decks."""
        self._queue = []
        for tile, widget, _started in self._building:
            try:
                widget.hide()
                widget.deleteLater()
            except RuntimeError:
                pass
        self._building = []
        for s in self._sections:
            for t in s[5]:
                if t.choice.family != "text":
                    t._pixmap = None
                    t.update()
        self._finish_queue()
        self.start_previews()

    def _qss(self):
        c = self.colors
        return (
            " QLabel#dd_gallery_title { font-size: 16px; font-weight: 600; background: transparent; }"
            f" QLabel#dd_gallery_sub {{ color: {_rgba(c['muted'])}; background: transparent; }}"
            f" QLabel#dd_gallery_head {{ font-size: 11px; font-weight: 700; letter-spacing: 0.6px;"
            f" color: {_rgba(c['muted'])}; padding-top: 10px; padding-bottom: 2px; background: transparent; }}"
            f" QWidget#dd_gallery_seg {{ background: {_rgba(c['card'])}; border: 1px solid {_rgba(c['line'])};"
            " border-radius: 7px; }"
            " QPushButton#dd_gallery_seg_btn { border: none; border-radius: 5px; padding: 4px 12px;"
            " background: transparent; min-height: 0; }"
            f" QPushButton#dd_gallery_seg_btn:hover {{ background: {_rgba(c['hover'])}; }}"
            f" QPushButton#dd_gallery_seg_btn:checked {{ background: {_rgba(c['accent_soft'])};"
            f" color: {_rgba(c['text'])}; font-weight: 600; }}"
            " QWidget#dd_gallery_body, QWidget#dd_gallery_side { background: transparent; }"
            f" QFrame#dd_gallery_rule {{ background: {_rgba(c['line'])}; border: none; margin: 0 8px; }}"
            f" QLabel#dd_gallery_group {{ color: {_rgba(c['muted'])}; font-size: 11px; padding: 2px 8px;"
            " background: transparent; }"
            " QPushButton#dd_gallery_nav { border: none; background: transparent; min-height: 0; }"
        )

    # -- content --------------------------------------------------------------------------

    def _section(self, key, family, title):
        head = QLabel(upper(title))
        head.setObjectName("dd_gallery_head")
        head.setProperty("dd_title", title)
        grid_w = QWidget()
        grid = QGridLayout(grid_w)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(_SPACING)
        grid.setVerticalSpacing(_SPACING)
        grid.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._body_lay.addWidget(head)
        self._body_lay.addWidget(grid_w)
        # The list on the left in three blocks (charts, stat cards, text), a thin line
        # between them; the stat card groups under a small "Stat cards" title.
        last = self._sections[-1][1] if self._sections else None
        if last is not None and last != family:
            line = QFrame()
            line.setObjectName("dd_gallery_rule")
            line.setFixedHeight(1)
            self._side.addSpacing(6)
            self._side.addWidget(line)
            self._side.addSpacing(6)
        if family == "stat" and last != "stat":
            group = QLabel(tr("Stat cards"))
            group.setObjectName("dd_gallery_group")
            self._side.addWidget(group)
        nav = _NavButton(self, title)
        nav.setObjectName("dd_gallery_nav")
        nav.setCheckable(True)
        nav.setCursor(Qt.CursorShape.PointingHandCursor)
        nav.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        nav.clicked.connect(lambda _=False, k=key: self._scroll_to(k))
        self._side.addWidget(nav)
        self._nav[key] = nav
        tiles = []
        self._sections.append((key, family, head, grid_w, grid, tiles))
        return grid_w, tiles

    def _build(self):
        from collections import Counter

        pins = WidgetRegistry.get_all()
        types = {d.get("type") for d in pins}
        stats = {d.get("stat_key") for d in pins if d.get("type") == "stat_card"}
        # How many of each on the main screen (its gallery: a click adds one more).
        counts = None if self.toggle or self._taken is not None else Counter(
            ("stat_card", d.get("stat_key")) if d.get("type") == "stat_card" else (d.get("type"), None) for d in pins
        )

        if self._taken is not None:
            types = self._taken
        for i, (group, charts) in enumerate(chart_groups()):
            charts = [c for c in charts if self._only is None or c[0] in self._only]
            if not charts:
                continue
            grid_w, tiles = self._section("charts" if i == 0 else f"charts:{group}", "chart", tr_name(group))
            for wtype, label in charts:
                name = tr_name(label)
                tiles.append(_Tile(self, grid_w, Choice(wtype, label), name, _CHART_PIC,
                                   f"{name} {tr_name(group)} {tr('Chart')}", pinned=wtype in types,
                                   count=counts[(wtype, None)] if counts is not None else None))
        if self._only is not None and self._stats is None:
            self._finish_queue()
            return
        if self._stats_taken is not None:
            stats = self._stats_taken
        for group, attrs in STAT_GROUPS:
            keys = [getattr(Config, attr, None) for attr in attrs]
            keys = [k for k in keys if k is not None and (self._stats is None or k in self._stats)]
            if not keys:
                continue
            grid_w, tiles = self._section(f"stats:{group}", "stat", tr_name(group))
            for key in keys:
                title = get_stat_card_default_title(key)
                choice = Choice("stat_card", get_stat_card_name(key), stat_key=key)
                tiles.append(_Tile(self, grid_w, choice, title, _STAT_PIC, f"{title} {tr_name(group)} {tr('Stat card')}",
                                   show_name=False, pinned=key in stats,
                                   count=counts[("stat_card", key)] if counts is not None else None))
        if self.toggle:
            self._finish_queue()
            return
        grid_w, tiles = self._section("text", "text", tr("Text"))
        text_tile = _Tile(self, grid_w, Choice("text_label", N_("Text Widget")), tr("Text Widget"), _TEXT_PIC,
                          f"{tr('Text Widget')} {tr('Text')}", show_name=False,
                          count=counts[("text_label", None)] if counts is not None else None)
        text_tile.put_text(tr("Write your own sentence, with live stats in it."))
        tiles.append(text_tile)
        self._finish_queue()

    def _finish_queue(self):
        self._queue = []
        data = _data_key(self.manager)
        now = time.monotonic()
        for s in self._sections:
            for t in s[5]:
                if t.choice.family == "text":
                    continue
                key = (t.choice.widget_type, t.choice.stat_key, t.pic_size, data, self.view_key())
                cached = _pictures.get(key)
                if cached is not None and now - cached[1] < _CACHE_S:
                    t.put_picture(cached[0])
                    continue
                self._queue.append(t)
        self._queue = self._nearest_first(self._queue)

    def _nearest_first(self, tiles):
        """Opened at the stat cards or the text: their previews (and the categories next to
        them) are built first, not the charts at the top that are not in view."""
        if not self._family or self._family == "chart":
            return tiles
        start = next((i for i, s in enumerate(self._sections) if s[1] == self._family), None)
        if start is None:
            return tiles
        where = {id(t): i for i, s in enumerate(self._sections) for t in s[5]}
        # The family's categories, then the ones above them (nearest first): on a stable sort
        # the tiles of one category keep their order.
        return sorted(tiles, key=lambda t: (where.get(id(t), 0) < start, abs(where.get(id(t), 0) - start)))

    def _filter(self, *_args):
        words = [w for w in self.search.text().lower().split() if w]
        any_shown = False
        only_missing = bool(_only_missing["on"])
        for key, family, head, grid_w, grid, tiles in self._sections:
            shown = [t for t in tiles if all(w in t.search_text for w in words)
                     and not (only_missing and t.pinned)]
            for t in tiles:
                grid.removeWidget(t)
                if t not in shown:
                    t.hide()
            cols = _COLUMNS[family]
            for i, t in enumerate(shown):
                grid.addWidget(t, i // cols, i % cols)
                t.show()
            head.setVisible(bool(shown))
            grid_w.setVisible(bool(shown))
            self._nav[key].setEnabled(bool(shown))
            self._nav[key].set_count(len(shown))
            head.setText(f"{upper(head.property('dd_title') or '')}  \u00b7  {len(shown)}")
            any_shown = any_shown or bool(shown)
        if not any_shown:
            self._empty.setText(tr("Everything is already added.") if (only_missing and not words)
                                else tr("No widget found."))
        self._empty.setVisible(not any_shown)
        visible = {id(t) for s in self._sections for t in s[5] if t.isVisibleTo(self)}
        self._queue.sort(key=lambda t: 0 if id(t) in visible else 1)
        QTimer.singleShot(0, self._fit_tail_room)

    def _set_only_missing(self, on):
        _only_missing["on"] = bool(on)
        for b, value in self._missing_btns:
            b.setChecked(value == bool(on))
        self._filter()

    def _scroll_to(self, key):
        for k, _f, head, *_rest in self._sections:
            if k == key and head.isVisibleTo(self):
                self._scroll.verticalScrollBar().setValue(max(0, head.y() - 4))
                break
        self._follow_scroll()

    def go_to(self, family):
        """Scroll to the first category of a family ("chart", "stat" or "text")."""
        key = next((s[0] for s in self._sections if s[1] == family), None)
        if key is not None:
            self._scroll_to(key)

    def _follow_scroll(self, *_args):
        """The list on the left marks the category at the top of the view."""
        bar = self._scroll.verticalScrollBar()
        y = bar.value() + 12
        shown = [s for s in self._sections if s[2].isVisibleTo(self)]
        current = None
        for key, _f, head, *_rest in shown:
            if head.y() <= y:
                current = key
        if current is None and shown:
            current = shown[0][0]
        for key, nav in self._nav.items():
            nav.setChecked(key == current)

    def _fit_tail_room(self):
        shown = [s for s in self._sections if s[2].isVisibleTo(self)]
        room = 0
        if shown:
            last_head, last_grid = shown[-1][2], shown[-1][3]
            last_h = last_grid.y() + last_grid.height() - last_head.y()
            room = max(0, self._scroll.viewport().height() - last_h - 8)
        if self._tail.height() != room:
            self._tail.setFixedHeight(room)
        self._follow_scroll()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_tail"):
            QTimer.singleShot(0, self._fit_tail_room)

    def set_where(self, where):
        """The line saying where the widget goes (the guided tour shows both ways)."""
        self._where_label.setText(tr_name(_WHERE.get(where, _WHERE[None])))

    def tile_for(self, predicate):
        """The tile of the first choice predicate(choice) accepts, or None."""
        for s in self._sections:
            for t in s[5]:
                if predicate(t.choice):
                    return t
        return None

    def prioritize(self, tile):
        """Build this tile's preview next (the guided tour shows it)."""
        if tile in self._queue:
            self._queue.remove(tile)
            self._queue.insert(0, tile)

    # -- previews -------------------------------------------------------------------------

    def _shimmer_step(self):
        self.shimmer = (self.shimmer + 0.035) % 1.0
        waiting = [t for s in self._sections for t in s[5]
                   if t._pixmap is None and t._text is None and t.isVisibleTo(self)]
        if not waiting and not self._queue and not self._building:
            self._shimmer_timer.stop()
        for t in waiting:
            if not t.visibleRegion().isEmpty():  # only the ones in view are repainted
                t.update()

    def start_previews(self):
        if (self._queue or self._building) and not self._shimmer_timer.isActive():
            self._shimmer_timer.start()
        if self._queue and not self._timer.isActive():
            self._stage.show()
            self._timer.start()  # the first build on its first tick: the window paints before

    def showEvent(self, event):
        super().showEvent(event)
        self.search.setFocus(Qt.FocusReason.OtherFocusReason)  # typing searches at once
        self.start_previews()

    def _add_first(self):
        """Enter in the search field: the first widget shown is added."""
        if not self.search.text().strip():
            return
        for s in self._sections:
            for t in s[5]:
                if t.isVisibleTo(self):
                    self.pick(t.choice, t)
                    return

    def _tick(self):
        now = time.monotonic()
        for entry in list(self._building):
            tile, widget, started = entry
            if _ready(widget) or now - started > _WAIT_MAX:
                self._building.remove(entry)
                self._finish(tile, widget)
        while self._queue and len(self._building) < _AT_ONCE:
            # The tiles in view first (scrolled to the stat cards: theirs, not the charts').
            idx = next((i for i, t in enumerate(self._queue) if not t.visibleRegion().isEmpty()), 0)
            tile = self._queue.pop(idx)
            try:
                build = _CHART_BUILD if tile.choice.family == "chart" else _STAT_BUILD
                widget = _make_preview(self.manager, tile.choice, self._stage, build, self.fields_for(tile.choice))
            except Exception:
                widget = None
                log_swallowed()
            if widget is not None:
                widget.move(0, len(self._building) * _CHART_BUILD[1])
                widget.show()
                _skip_animations(widget)
                self._building.append((tile, widget, now))
        if not self._queue and not self._building:
            self._timer.stop()

    def _finish(self, tile, widget):
        try:
            pm = _picture(widget, _inner(tile))
            tile.put_picture(pm)
            if not pm.isNull():
                key = (tile.choice.widget_type, tile.choice.stat_key, tile.pic_size, _data_key(self.manager),
                       self.view_key())
                _pictures[key] = (pm, time.monotonic())
        except RuntimeError:
            pass
        except Exception:
            log_swallowed()
        try:
            widget.hide()
            widget.deleteLater()
        except RuntimeError:
            pass

    def pick(self, choice, tile=None):
        if self.toggle:
            if tile is not None:
                tile.set_pinned(not tile.pinned)
                if self._on_toggle is not None:
                    try:
                        self._on_toggle(choice, tile.pinned)
                    except Exception:
                        log_swallowed()
            return
        self.choice = choice
        if self._on_add is not None:
            # A click adds one more (several of a kind are fine: other periods, other decks);
            # the tile's "−" takes one off (remove_one).
            new_id = None
            choice.time_span, choice.custom_days, choice.deck_ids = self.fields_for(choice)
            try:
                new_id = self._on_add(choice)
            except Exception:
                log_swallowed()
            if tile is not None and new_id:
                self._added.setdefault(tile, []).append(new_id)
                tile.set_count(tile.count + 1)
            # The main screen rebuilt behind it: keep the gallery in front.
            QTimer.singleShot(0, self._to_front)
            return
        self.accept()

    def _reset(self):
        try:
            charts, stats = self._on_reset()
        except Exception:
            log_swallowed()
            return
        charts, stats = set(charts), set(stats)
        for s in self._sections:
            for t in s[5]:
                if t.choice.family == "chart":
                    t.set_pinned(t.choice.widget_type in charts)
                elif t.choice.family == "stat":
                    t.set_pinned(t.choice.stat_key in stats)
        QTimer.singleShot(0, self._to_front)

    def remove_one(self, tile):
        """Take one of tile's widgets off the main screen: the last one added from here, else
        the last of its kind on the screen. Cancel puts it back."""
        if self._on_remove is None or tile.count <= 0:
            return
        ids = self._added.get(tile) or []
        if ids:
            wid = ids.pop()
        else:
            choice = tile.choice
            mine = [d.get("id") for d in WidgetRegistry.get_all()
                    if d.get("type") == choice.widget_type
                    and (choice.widget_type != "stat_card" or d.get("stat_key") == choice.stat_key)]
            wid = mine[-1] if mine else None
        if not wid:
            return
        try:
            self._on_remove(wid)
        except Exception:
            log_swallowed()
            return
        tile.set_count(tile.count - 1)
        QTimer.singleShot(0, self._to_front)

    def _to_front(self):
        try:
            self.raise_()
            self.activateWindow()
        except RuntimeError:
            pass

    def marked(self):
        """(chart types, stat card keys) marked (toggle mode)."""
        charts, stats = set(), set()
        for s in self._sections:
            for t in s[5]:
                if not t.pinned:
                    continue
                if t.choice.family == "stat":
                    stats.add(t.choice.stat_key)
                elif t.choice.family == "chart":
                    charts.add(t.choice.widget_type)
        return charts, stats

    def done(self, result):
        self._queue = []
        self._timer.stop()
        self._shimmer_timer.stop()
        try:
            QApplication.instance().removeEventFilter(self._guard)
        except RuntimeError:
            pass
        super().done(result)


def _make_preview(manager, choice, stage, size, fields=(None, None, None)):
    """The widget, built for the deck shown at size inside stage (its data may still come).
    fields: (time_span, custom_days, deck_ids) chosen in the gallery (None: the default)."""
    from ...widget_factory.factory import WidgetFactory

    widget_def = {
        "id": f"dd_gallery:{choice.widget_type}:{choice.stat_key or ''}",
        "type": choice.widget_type,
        "label": choice.label,
        "stat_key": choice.stat_key,
    }
    span, days, deck_ids = fields
    if span is None:
        span = default_span(choice.widget_type, choice.stat_key)  # as it will be added
    if span is not None:
        widget_def["time_span"] = span
        if days is not None:
            widget_def["custom_days"] = days
    if deck_ids:
        widget_def["deck_ids"] = list(deck_ids)
    norm = manager._normalized_widget_def(widget_def)
    deck_id = getattr(manager, "_current_deck_id", None)
    widget = WidgetFactory.create(
        norm,
        deck_id=deck_id,
        cache=manager.__class__._global_history_cache,
        parent=stage,
        cfg=manager._config_manager,
    )
    if widget is None:
        return None
    # Some builders make their card without a parent: shown as is, it would be a window
    # of its own on the screen.
    if widget.parentWidget() is not stage:
        widget.setParent(stage)
    widget.setMinimumSize(0, 0)
    widget.setMaximumSize(16777215, 16777215)
    widget.setFixedSize(*size)
    # A picture is taken: no intro animation to wait for.
    for chart in [widget, *widget.findChildren(QWidget)]:
        if hasattr(chart, "_finish_without_animation"):
            chart.setProperty("deepdivestats_skip_next_show_anim", True)
    if getattr(widget, "_is_loading", False):
        manager._trigger_async_widget_update(widget, norm, deck_id)
    return widget


def _skip_animations(widget):
    """Charts drawn at their end state at once: only one picture is taken."""
    for chart in [widget, *widget.findChildren(QWidget)]:
        finish = getattr(chart, "_finish_without_animation", None)
        if callable(finish):
            try:
                finish()
            except Exception:
                log_swallowed()


def _data_key(manager):
    """The deck shown and the collection's last change: a kept picture is reused only for
    the same deck and the same data."""
    try:
        mod = mw.col.mod
    except Exception:
        mod = None
    return getattr(manager, "_current_deck_id", None), mod


def _ready(widget):
    """Its data is there and its charts are drawn to the end."""
    try:
        for chart in [widget, *widget.findChildren(QWidget)]:
            if getattr(chart, "_is_loading", False):
                return False
            # Charts that read their data in the background (Introduced, Answer Time, Rating
            # by Interval, Week by Hour): taken before it came, their picture was empty.
            if getattr(chart, "_pending_key", None) is not None:
                return False
            progress = getattr(chart, "_progress", None)
            if isinstance(progress, (int, float)) and progress < 1.0:
                return False
        return True
    except RuntimeError:
        return True


_CHART_INSET = (10, 8)  # room inside a chart's frame: its axis labels do not touch it


def _inner(tile):
    """The size a tile's picture is drawn at (inside its frame for a chart)."""
    w, h = tile.pic_size
    if tile.choice.family == "chart":
        return w - 2 * _CHART_INSET[0], h - 2 * _CHART_INSET[1]
    return w, h


def _picture(widget, size):
    """A chart: its card body (the name is under the tile), shrunk to size. A stat card:
    the whole card (its title is part of it)."""
    body = getattr(widget, "body_widget", None) or widget
    if body is not widget and (body.width() <= 0 or body.height() <= 0):
        body = widget
    # Drawn on a see-through picture, without the window's background: around a card's
    # rounded corners the picture stays empty.
    dpr = body.devicePixelRatioF() or 1.0
    shown_dpr = dpr
    if (body.width(), body.height()) != tuple(size):
        dpr *= 2  # drawn twice as fine, then shrunk: the small axis numbers stay sharp
    pm = QPixmap(max(1, int(round(body.width() * dpr))), max(1, int(round(body.height() * dpr))))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    body.render(pm, QPoint(0, 0), QRegion(), QWidget.RenderFlag.DrawChildren)
    target = QSize(int(size[0] * shown_dpr), int(size[1] * shown_dpr))
    if pm.size() == target:
        return pm  # already at its size: kept as is, sharp
    out = pm.scaled(target, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    out.setDevicePixelRatio(shown_dpr)
    return out if not out.isNull() else QPixmap()


def open_widget_gallery(manager, on_pick, family=None, where=None, only=None, taken=None, parent=None,
                        on_remove=None):
    """Open the gallery (at the categories of family: "chart", "stat" or "text"; where: the
    kind of spot the widget goes to, for the line under the title). on_pick(Choice) -> id runs
    for each widget clicked: it is added at once and the gallery stays open, to add several;
    on_remove(id) when one is clicked again. True when closed with Done (Cancel: the caller
    undoes them). parent: the window it opens over (Anki's by default)."""
    dialog = WidgetGallery(manager, parent or mw, family=family, where=where, only=only, taken=taken,
                           on_add=on_pick, on_remove=on_remove)
    try:
        from .....ui.config.shared.dialog_sizing import show_when_painted

        show_when_painted(dialog)
    except Exception:
        log_swallowed()
    accepted = dialog.exec()
    dialog.deleteLater()
    return bool(accepted)


def open_manage_gallery(manager, parent, charts, charts_shown, stats, stats_shown, family=None, on_toggle=None,
                        on_reset=None):
    """The gallery as the manager of a set of widgets (Deep Dive): every chart type of charts
    and stat card key of stats, the shown ones checked; a click checks or unchecks one and
    on_toggle(choice, checked) applies it at once. (chart types, stat card keys) checked
    once closed with Done, else None (Cancel: the caller undoes the changes)."""
    dialog = WidgetGallery(manager, parent or mw, family=family, only=charts, taken=charts_shown,
                           stats=stats, stats_taken=stats_shown, toggle=True, on_toggle=on_toggle,
                           on_reset=on_reset)
    try:
        from .....ui.config.shared.dialog_sizing import show_when_painted

        show_when_painted(dialog)
    except Exception:
        log_swallowed()
    accepted = dialog.exec()
    result = dialog.marked() if accepted else None
    dialog.deleteLater()
    return result
