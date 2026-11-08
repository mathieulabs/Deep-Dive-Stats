# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""What each chart shows, in a few words: the "?" next to its title (hover to read it), and
the widget gallery's tile tooltips. Settings > General can hide the "?"
(Config.SHOW_CHART_HELP)."""

from aqt.qt import QEvent, QLabel, QObject, QSize, Qt, QTimer, QWidget

from ....i18n import N_, tr_name

HELP = {
    "activity": N_(
        "Reviews done each day. Breakdown by Type splits them:\n"
        "• Learning: new cards in their learning steps.\n"
        "• Relearning: forgotten cards in their relearning steps.\n"
        "• Young: reviews of cards with an interval under 21 days.\n"
        "• Mature: reviews of cards with an interval of 21 days or more.\n"
        "• Filtered: reviews in filtered decks that leave the schedule as it was."
    ),
    "retention": N_(
        "Share of answers other than Again, each day:\n"
        "• All: every answer, learning steps included.\n"
        "• Young: answers on cards whose interval was 1 to 20 days.\n"
        "• Mature: answers on cards whose interval was 21 days or more.\n"
        "• True: young and mature together, learning steps left out (Anki's True Retention)."
    ),
    "distribution": N_(
        "Answer buttons pressed in the period:\n"
        "• Learning: cards in their learning or relearning steps.\n"
        "• Young: cards with an interval under 21 days.\n"
        "• Mature: cards with an interval of 21 days or more."
    ),
    "card_counts": N_("Your cards by state: new, learning, relearning, young, mature, suspended and buried."),
    "hourly": N_("Reviews by hour of the day, with the success rate at each hour."),
    "future_due": N_("Cards due on each coming day. Backlog: overdue cards.\nBreakdown by Type: learning, young (interval under 21 days) and mature cards.\nBreakdown by Result: the reviews FSRS expects you to pass or fail."),
    "review_intervals": N_("Cards by their current interval: the days between their last review and the next one."),
    "stability": N_("Cards by FSRS stability: the number of days after which the chance of recalling them "
                    "falls to 90%."),
    "difficulty": N_("Cards by FSRS difficulty: how hard each card is to remember, from easiest to hardest."),
    "retrievability": N_("Cards by FSRS retrievability: the chance of recalling each card right now."),
    "ratings": N_("Answer buttons pressed each day. Show as % gives each button's share."),
    "answer_time": N_("Reviews by time taken to answer, one bar per second (the last bar: 60 s or more), split by rating. By Card Type: learning, young and mature cards."),
    "interval_ratings": N_("Reviews by the card's interval at the time of the answer, split by rating. Learning steps are left out."),
    "forgotten": N_("Young and mature cards answered Again each day."),
    "introduced": N_("New cards seen for the first time each day. Re-introduced: cards seen again after a reset. By First Rating: the answer given that first time."),
    "interval_load": N_("Average reviews per day caused by the cards of each interval: a card with a 10-day interval adds 0.1 review a day."),
    "lapse_distribution": N_("Cards by the number of times they were forgotten (lapses)."),
    "card_states": N_("Your cards by state on each past day, rebuilt from your review history. Deleted cards are not counted."),
    "week_hours": N_("Reviews by day of the week and hour: the darker the cell, the more reviews."),
    "learning_steps": N_("Learning answers each card needed before it first became a review card. Cards still in learning are left out; cards that skipped learning are counted apart."),
    "due_today": N_("Learning cards due today, by the hour they come due. Due now includes Anki's learn ahead limit."),
}


def help_text(chart_type):
    """The explanation of a chart type, translated ("" when there is none)."""
    text = HELP.get(str(chart_type or ""))
    return tr_name(text) if text else ""


def help_enabled():
    try:
        from aqt import mw
        from ...ui import Config, ConfigManager

        return bool(ConfigManager(mw).config.get(Config.SHOW_CHART_HELP, True))
    except Exception:
        return True


class _HelpIcon(QLabel):
    """The "?": its text in the add-on's own tooltip (as the charts'), shown at once on hover.

    Shown only while the mouse is over its chart (the card), so the headers stay as they were
    at rest; its place stays reserved (see-through, not hidden) so the title never moves."""

    _REST, _SHOWN = 0.0, 0.55

    def __init__(self, parent, text):
        super().__init__(parent)
        self._card = None
        import textwrap

        # One line per paragraph (a "\n" in the text), long ones wrapped.
        self._lines = [{"text": line} for para in text.split("\n") for line in (textwrap.wrap(para, 64) or [""])]
        self._tip = None

    def enterEvent(self, event):
        super().enterEvent(event)
        try:
            from ..chart_utils.tooltip import TooltipWindow, show_tooltip_near

            if self._tip is None:
                self._tip = TooltipWindow(self)
            show_tooltip_near(self, self._tip, self.rect().bottomRight(), lines=self._lines,
                              x_offset=6, y_offset=6, show_only_if_hidden=False)
        except Exception:
            from ...logic.logger import log_swallowed

            log_swallowed()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        if self._tip is not None:
            self._tip.hide()

    def hideEvent(self, event):
        if self._tip is not None:
            self._tip.hide()
        super().hideEvent(event)

    def refresh_icon(self):
        """Drawn in the theme of where it is now (a pinned chart in the pinned theme): made
        before its header was put in its card, it took the Deep Dive theme."""
        try:
            from ...ui.theme.icons import get_svg_icon

            icon = get_svg_icon("help-circle", size=14, context_ref=self)
            self.setPixmap(icon.pixmap(QSize(14, 14)))
        except RuntimeError:
            pass

    def changeEvent(self, event):
        from aqt.qt import QEvent

        if event.type() == QEvent.Type.ParentChange:
            self.refresh_icon()
        super().changeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_icon()
        if self._card is None:
            # The chart's card: the first parent that is a card (main screen or Deep Dive).
            w = self.parentWidget()
            card = None
            while w is not None:
                if w.objectName() == "pinned_widget_card" or type(w).__name__ == "ResizableWrapper":
                    card = w
                    break
                w = w.parentWidget()
            self._card = card or self.parentWidget()
            if self._card is not None:
                self._card.installEventFilter(self)
        self._set_shown(self._mouse_on_card())

    def _mouse_on_card(self):
        from aqt.qt import QCursor

        card = self._card
        try:
            return bool(card is not None and card.isVisible()
                        and card.rect().contains(card.mapFromGlobal(QCursor.pos())))
        except RuntimeError:
            return False

    def _set_shown(self, on):
        if getattr(self, "_muted", False):
            on = False
        effect_opacity(self, self._SHOWN if on else self._REST)

    def eventFilter(self, obj, event):
        from aqt.qt import QEvent

        if obj is self._card:
            if event.type() == QEvent.Type.Enter:
                self._set_shown(True)
            elif event.type() == QEvent.Type.Leave:
                self._set_shown(self._mouse_on_card())
        return False


class _RoomWatcher(QObject):
    """Places the "?" in its header without taking any room: it floats at the start of the
    header's free space (the stretch after the title, stats and labels), so no button ever
    moves for it. When that free space is too short (a narrow card), it hides: it is the
    first thing to go, before the title elides or the buttons gather."""

    GAP = 4

    def __init__(self, header, btn):
        super().__init__(header)
        self._header = header
        self._btn = btn
        self._queued = False
        header.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.Resize, QEvent.Type.LayoutRequest, QEvent.Type.Show):
            self.queue()
        return False

    def queue(self):
        # After the layout has placed its items (their geometry is not final yet here).
        if self._queued:
            return
        self._queued = True
        QTimer.singleShot(0, self.check)

    def _gap(self, lay, owner):
        """(x, width) in the header of the first stretch at least as wide as the "?"."""
        need = self._btn.width() + 2 * self.GAP
        for i in range(lay.count()):
            item = lay.itemAt(i)
            sp = item.spacerItem()
            if sp is not None:
                g = sp.geometry()
                if g.width() >= need and sp.expandingDirections() & Qt.Orientation.Horizontal:
                    x = owner.mapTo(self._header, g.topLeft()).x() if owner is not self._header else g.x()
                    return x, g.width()
                continue
            w = item.widget()
            # QWidget.layout(w): some widgets keep their layout in an attribute named layout.
            sub = item.layout() if w is None else (QWidget.layout(w) if w.isVisible() else None)
            if sub is not None:
                found = self._gap(sub, owner if w is None else w)
                if found:
                    return found
        return None

    def check(self):
        self._queued = False
        try:
            lay = self._header.layout()
            btn = self._btn
            if lay is None or btn is None:
                return
            found = self._gap(lay, self._header)
            if not found:
                btn.hide()
                return
            x, _w = found
            btn.move(int(x + self.GAP), int((self._header.height() - btn.height()) / 2))
            btn.show()
            btn.raise_()
        except RuntimeError:
            pass
        except Exception:
            from ...logic.logger import log_swallowed

            log_swallowed()  # never an error dialog for the "?"


def insert_help_button(header, chart_type):
    """Put the "?" in a chart header, right after its left part (title, labels, stats), at the
    same place on every chart, pinned or in Deep Dive. It floats over the header's free space
    and takes no room: no button moves for it (see _RoomWatcher)."""
    lay = header.layout() if header is not None else None
    if lay is None:
        return None
    btn = make_help_button(header, chart_type)
    if btn is None:
        return None
    btn.hide()
    header._help_room = _RoomWatcher(header, btn)
    header._help_room.queue()
    return btn


def make_help_button(parent, chart_type):
    """The small "?" next to a chart's title: its explanation shows on hover. None when the
    chart has none or the "?" are hidden in the settings."""
    text = help_text(chart_type)
    if not text or not help_enabled():
        return None
    from ...ui.theme.icons import get_svg_icon

    label = _HelpIcon(parent, text)
    label.setObjectName("chart_help")
    icon = get_svg_icon("help-circle", size=14, context_ref=parent)
    label.setPixmap(icon.pixmap(QSize(14, 14)))
    label.setFixedSize(16, 16)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setCursor(Qt.CursorShape.WhatsThisCursor)
    label.setMouseTracking(True)
    effect_opacity(label, 0.0)  # shown while the mouse is over the chart (see _HelpIcon)
    return label


def effect_opacity(widget, value):
    """Quiet, as the other header icons (one effect, its opacity changed)."""
    try:
        from aqt.qt import QGraphicsOpacityEffect

        eff = widget.graphicsEffect()
        if not isinstance(eff, QGraphicsOpacityEffect):
            eff = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(eff)
        eff.setOpacity(value)
    except Exception:
        pass


def set_help_muted(icon, muted):
    """Hide the "?" (see more_button: "⋯" goes first when both want the same spot)."""
    try:
        icon._muted = bool(muted)
        if muted:
            effect_opacity(icon, 0.0)
            tip = getattr(icon, "_tip", None)
            if tip is not None:
                tip.hide()
        else:
            icon._set_shown(icon._mouse_on_card())
    except (RuntimeError, AttributeError):
        pass


class _HelpPopup(QObject):
    """A chart's explanation from its right-click menu, in the add-on's tooltip, until the
    next click or key."""

    _current = None

    def __init__(self, anchor, text):
        super().__init__(anchor)
        import textwrap

        from aqt.qt import QApplication, QCursor
        from ..chart_utils.tooltip import TooltipWindow, show_tooltip_near

        lines = [{"text": line} for para in text.split("\n") for line in (textwrap.wrap(para, 64) or [""])]
        self._tip = TooltipWindow(anchor)
        pos = anchor.mapFromGlobal(QCursor.pos())
        show_tooltip_near(anchor, self._tip, pos, lines=lines, x_offset=10, y_offset=10, show_only_if_hidden=False)
        QApplication.instance().installEventFilter(self)
        _HelpPopup._current = self

    def eventFilter(self, _obj, event):
        if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress, QEvent.Type.Wheel,
                            QEvent.Type.WindowDeactivate):
            self.close()
        return False

    def close(self):
        from aqt.qt import QApplication

        try:
            QApplication.instance().removeEventFilter(self)
            self._tip.hide()
            self._tip.deleteLater()
        except RuntimeError:
            pass
        if _HelpPopup._current is self:
            _HelpPopup._current = None
        self.deleteLater()


def add_help_action(menu, chart_type, anchor):
    """"About This Chart" in a chart's right-click menu (its "?" text): the "?" only shows
    where the title row has room. Nothing when the chart has no explanation."""
    text = help_text(chart_type)
    if not text:
        return None
    from ...ui.theme.icons import get_svg_icon
    from ....i18n import tr

    act = menu.addAction(tr("About This Chart"))
    act.setIcon(get_svg_icon("help-circle", size=16, context_ref=menu))

    def _show():
        old = _HelpPopup._current
        if old is not None:
            old.close()
        # After the menu has closed (its own click would close the popup at once).
        QTimer.singleShot(0, lambda: _HelpPopup(anchor, text))

    act.triggered.connect(_show)
    return act
