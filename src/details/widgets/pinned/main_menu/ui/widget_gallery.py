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
from .add_widget_menu import CHARTS, STAT_GROUPS, Choice, default_span
from ... import WidgetRegistry
from ....stats_cards.logic.model import get_stat_card_default_title, get_stat_card_name
from ....stats_cards.ui.style import CARD_CORNER_RADIUS_PX
from .....logic.logger import log_debug, log_swallowed
from ......qss import set_qss
from ......i18n import N_, tr, tr_name

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

_WHERE = {
    None: N_("It goes at the end of the main screen."),
    "after": N_("It goes right after the widget you right clicked."),
    "end": N_("It goes at the end of the line."),
    "newline": N_("It goes on a new line, where you clicked."),
    "newbox": N_("It goes in a new box, where you clicked."),
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
    }


def _rgba(c):
    return f"rgba({c.red()},{c.green()},{c.blue()},{c.alpha()})"


class _Tile(QWidget):
    """A preview, its name under it (stat cards show theirs in the picture), a check mark
    when it is on the main screen already. Drawn by hand: one widget, one click."""

    def __init__(self, gallery, parent, choice, name, pic_size, search_text, show_name=True, pinned=False):
        super().__init__(parent)  # in its grid from the start: a widget shown without a parent is a window
        self.gallery = gallery
        self.choice = choice
        self.name = name
        self.pic_size = pic_size
        self.search_text = search_text.lower()
        self.pinned = pinned
        self._show_name = show_name
        self._pixmap = None
        self._text = None
        self._hover = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tr("Already on the main screen") if pinned else "")
        name_h = QFontMetrics(self.font()).height() + _NAME_GAP if show_name else 0
        self.setFixedSize(pic_size[0], pic_size[1] + name_h)

    def pic_rect(self):
        return QRectF(0, 0, self.pic_size[0], self.pic_size[1])

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
            self.gallery.pick(self.choice)
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
            if self.pinned:
                r = 7.0
                center = QPointF(pic.right() - r - 6, pic.top() + r + 6)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(0, 0, 0, 120))
                p.drawEllipse(center, r, r)
                pen = QPen(QColor(255, 255, 255), 1.6)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(pen)
                p.drawPolyline([QPointF(center.x() - 3.2, center.y() + 0.2),
                                QPointF(center.x() - 0.8, center.y() + 2.6),
                                QPointF(center.x() + 3.4, center.y() - 2.4)])
            if self._show_name:
                p.setFont(self.font())
                p.setPen(c["text"])
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
    def __init__(self, manager, parent=None, family=None, where=None):
        super().__init__(parent or mw)
        self.manager = manager
        self.choice = None
        self.colors = _colors()
        self._queue = []
        self._building = []  # (tile, widget, started at)
        self._sections = []  # (key, family, header, grid widget, grid, tiles)
        self._nav = {}       # section key: sidebar button
        self.setWindowTitle(tr("Add Widget"))
        self.setProperty("deepdivestats_theme_context", "pinned")
        self.setProperty("deepdivestats_ignore_forced_dark_theme", True)
        try:
            from ....chart_utils.theme import settings_dialog_qss_for

            set_qss(self, settings_dialog_qss_for(ThemeContext.PINNED, default=ThemeContext.PINNED) + self._qss())
        except Exception:
            log_swallowed()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 14)
        outer.setSpacing(12)

        self.search = QLineEdit(self)
        self.search.setPlaceholderText(tr("Search widgets..."))
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(_SIDEBAR_W)  # under the list of categories, the same width
        self.search.textChanged.connect(self._filter)
        self.search.returnPressed.connect(self._add_first)

        main = QHBoxLayout()
        main.setSpacing(18)
        self._side = QVBoxLayout()
        self._side.setContentsMargins(0, 6, 0, 0)
        self._side.setSpacing(2)
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
        self._body_lay.setSpacing(10)
        scroll.setWidget(body)
        scroll.verticalScrollBar().valueChanged.connect(self._follow_scroll)
        self._scroll = scroll
        main.addWidget(scroll, 1)
        outer.addLayout(main, 1)

        foot = QHBoxLayout()
        foot.setSpacing(18)  # as between the list and the widgets: the line starts under them
        foot.addWidget(self.search)
        self._where_label = QLabel(tr_name(_WHERE.get(where, _WHERE[None])))
        self._where_label.setObjectName("dd_gallery_sub")
        foot.addWidget(self._where_label, 1)
        cancel = QPushButton(tr("Cancel"))
        cancel.setAutoDefault(False)  # Enter adds the first widget found (see _add_first)
        cancel.clicked.connect(self.reject)
        foot.addWidget(cancel)
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
        self.setFixedWidth(32 + _SIDEBAR_W + 18 + grid_w + 10 + bar + 4)
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

    def _qss(self):
        c = self.colors
        return (
            f" QLabel#dd_gallery_sub {{ color: {_rgba(c['muted'])}; background: transparent; }}"
            " QLabel#dd_gallery_head { font-weight: 600; padding-top: 6px; background: transparent; }"
            " QWidget#dd_gallery_body, QWidget#dd_gallery_side { background: transparent; }"
            f" QFrame#dd_gallery_rule {{ background: {_rgba(c['line'])}; border: none; margin: 0 8px; }}"
            f" QLabel#dd_gallery_group {{ color: {_rgba(c['muted'])}; font-size: 11px; padding: 2px 8px;"
            " background: transparent; }"
            " QPushButton#dd_gallery_nav { text-align: left;"
            " padding: 5px 8px; border: none; border-radius: 4px; background: transparent; }"
            f" QPushButton#dd_gallery_nav:hover {{ background: {_rgba(c['card'])}; }}"
            f" QPushButton#dd_gallery_nav:checked {{ background: {_rgba(c['hover'])}; }}"
            f" QPushButton#dd_gallery_nav:disabled {{ color: {_rgba(c['line'])}; }}"
        )

    # -- content --------------------------------------------------------------------------

    def _section(self, key, family, title):
        head = QLabel(title)
        head.setObjectName("dd_gallery_head")
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
        nav = QPushButton(title)
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
        pins = WidgetRegistry.get_all()
        types = {d.get("type") for d in pins}
        stats = {d.get("stat_key") for d in pins if d.get("type") == "stat_card"}

        grid_w, tiles = self._section("charts", "chart", tr("Charts"))
        for wtype, label in CHARTS:
            name = tr_name(label)
            tiles.append(_Tile(self, grid_w, Choice(wtype, label), name, _CHART_PIC, f"{name} {tr('Chart')}",
                               pinned=wtype in types))
        for group, attrs in STAT_GROUPS:
            grid_w, tiles = self._section(f"stats:{group}", "stat", tr_name(group))
            for attr in attrs:
                key = getattr(Config, attr, None)
                if key is None:
                    continue
                title = get_stat_card_default_title(key)
                choice = Choice("stat_card", get_stat_card_name(key), stat_key=key)
                tiles.append(_Tile(self, grid_w, choice, title, _STAT_PIC, f"{title} {tr_name(group)} {tr('Stat card')}",
                                   show_name=False, pinned=key in stats))
        grid_w, tiles = self._section("text", "text", tr("Text"))
        text_tile = _Tile(self, grid_w, Choice("text_label", N_("Text Widget")), tr("Text Widget"), _TEXT_PIC,
                          f"{tr('Text Widget')} {tr('Text')}", show_name=False)
        text_tile.put_text(tr("Write your own sentence, with live stats in it."))
        tiles.append(text_tile)
        self._queue = []
        data = _data_key(self.manager)
        now = time.monotonic()
        for s in self._sections:
            for t in s[5]:
                if t.choice.family == "text":
                    continue
                key = (t.choice.widget_type, t.choice.stat_key, t.pic_size, data)
                cached = _pictures.get(key)
                if cached is not None and now - cached[1] < _CACHE_S:
                    t.put_picture(cached[0])
                    continue
                self._queue.append(t)

    def _filter(self, *_args):
        words = [w for w in self.search.text().lower().split() if w]
        any_shown = False
        for key, family, head, grid_w, grid, tiles in self._sections:
            shown = [t for t in tiles if all(w in t.search_text for w in words)]
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
            any_shown = any_shown or bool(shown)
        self._empty.setVisible(not any_shown)
        visible = {id(t) for s in self._sections for t in s[5] if t.isVisibleTo(self)}
        self._queue.sort(key=lambda t: 0 if id(t) in visible else 1)
        QTimer.singleShot(0, self._fit_tail_room)

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
                    self.pick(t.choice)
                    return

    def _tick(self):
        now = time.monotonic()
        for entry in list(self._building):
            tile, widget, started = entry
            if _ready(widget) or now - started > _WAIT_MAX:
                self._building.remove(entry)
                self._finish(tile, widget)
        while self._queue and len(self._building) < _AT_ONCE:
            tile = self._queue.pop(0)
            try:
                build = _CHART_BUILD if tile.choice.family == "chart" else _STAT_BUILD
                widget = _make_preview(self.manager, tile.choice, self._stage, build)
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
                key = (tile.choice.widget_type, tile.choice.stat_key, tile.pic_size, _data_key(self.manager))
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

    def pick(self, choice):
        self.choice = choice
        self.accept()

    def done(self, result):
        self._queue = []
        self._timer.stop()
        self._shimmer_timer.stop()
        try:
            QApplication.instance().removeEventFilter(self._guard)
        except RuntimeError:
            pass
        super().done(result)


def _make_preview(manager, choice, stage, size):
    """The widget, built for the deck shown at size inside stage (its data may still come)."""
    from ...widget_factory.factory import WidgetFactory

    widget_def = {
        "id": f"dd_gallery:{choice.widget_type}:{choice.stat_key or ''}",
        "type": choice.widget_type,
        "label": choice.label,
        "stat_key": choice.stat_key,
    }
    span = default_span(choice.widget_type, choice.stat_key)  # as it will be added
    if span is not None:
        widget_def["time_span"] = span
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


def open_widget_gallery(manager, on_pick, family=None, where=None):
    """Open the gallery (at the categories of family: "chart", "stat" or "text"; where: the
    kind of spot the widget goes to, for the line under the title). on_pick(Choice) runs
    once it is closed on a widget."""
    dialog = WidgetGallery(manager, mw, family=family, where=where)
    try:
        from .....ui.config.shared.dialog_sizing import show_when_painted

        show_when_painted(dialog)
    except Exception:
        log_swallowed()
    accepted = dialog.exec()
    choice = dialog.choice
    dialog.deleteLater()
    if accepted and choice is not None:
        on_pick(choice)
