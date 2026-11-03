# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Small labels in a pinned chart's title row: the period it shows ("Past Month ▾") and,
when it does not follow the current deck, the deck it reads ("Japanese ▾"). They say what
the card shows at a glance, and a click changes it without going through the right-click
menu. Both can be turned off (Settings > Pinned Widgets, or "Hide these labels").

They sit in the title row, right after the title: when the row is short the title elides
and the header stats fold into their icon, as they already do."""

from aqt.qt import (
    QBoxLayout, QColor, QEvent, QFont, QFontMetrics, QObject, QPainter, QPalette, QPen, QPoint, QPointF,
    QRectF, Qt, QTimer, QToolButton, QWidget,
)

from ..imports import Config, Period, mw
from ... import DeckMultiSelectDialog, WidgetRegistry
from .....ui import StyledMenu, get_svg_icon
from .....logic.logger import log_swallowed
from ......i18n import N_, tr, tr_n, tr_name

_TITLE_NAMES = ("pinned_header",)
_GAP = 8
_PAD = 7
_CHEVRON = 7

# Charts whose data has no period (counts, forecasts, the calendar has its own buttons).
NO_SPAN_TYPES = (
    "card_counts", "heatmap", "future_due", "review_intervals",
    "stability", "difficulty", "retrievability",
)


def has_time_span(widget_def):
    if not isinstance(widget_def, dict) or widget_def.get("type") in NO_SPAN_TYPES:
        return False
    return widget_def.get("stat_key") not in (Config.DASH_SHOW_STREAK, Config.DEEP_DIVE_SHOW_STREAK)


def span_text(manager, widget_def):
    """The name of the widget's period, as the period menu lists it."""
    norm = manager._normalized_widget_def(widget_def)
    span = norm.get("time_span", Period.TOTAL)
    days = norm.get("custom_days")
    try:
        span = int(span)
    except (TypeError, ValueError):
        return ""
    try:
        from .....logic.tabs import get_tabs_config

        for tab in get_tabs_config(manager._config_manager):
            if tab.get("range") != span:
                continue
            if span == Period.CUSTOM and tab.get("days") != days:
                continue
            return tr_name(tab.get("title") or N_("Stats"))
    except Exception:
        log_swallowed()
    if span == Period.CUSTOM and days:
        return tr_n("{n} day", "{n} days", int(days))
    label = Period.LABEL.get(span)
    return tr_name(label) if label else ""


def _explicit_decks(widget_def):
    deck_ids = widget_def.get("deck_ids")
    if deck_ids:
        return list(deck_ids)
    did = widget_def.get("deck_id")
    if isinstance(did, int) and did != 0:
        return [did]
    return None


def deck_text(manager, widget_def):
    """The deck(s) the widget reads, or "" when it follows the current deck."""
    decks = _explicit_decks(widget_def)
    if not decks:
        return ""
    from ...widget_factory.factory import _resolve_deck_ids

    context = getattr(manager, "_current_deck_id", None)
    resolved = _resolve_deck_ids(decks, context)
    if resolved == context:
        return ""
    if isinstance(resolved, list) and len(resolved) == 1:
        resolved = resolved[0]
    if resolved == -1 or resolved == "deleted":
        return tr_name(N_("Deleted Cards"))
    if isinstance(resolved, int):
        try:
            return mw.col.decks.name(resolved).split("::")[-1]
        except Exception:
            return ""
    return tr_n("{n} deck", "{n} decks", len(resolved))


# -- Actions shared with the right-click menu --------------------------------------------

def _latest(widget_def):
    """The widget's saved definition now: a menu can be built from one read before a change
    (a period picked a moment ago, its screen not rebuilt yet)."""
    wid = widget_def.get("id")
    return next((d for d in WidgetRegistry.get_all() if d.get("id") == wid), widget_def)


def set_span(manager, widget_def, span, days=None):
    updates = {"time_span": span}
    if days is not None:
        updates["custom_days"] = days
    manager._update_span_bulk(widget_def["id"], updates)


def apply_span_to_all(manager, widget_def):
    """Give every widget that has a period the period of this one."""
    norm = manager._normalized_widget_def(_latest(widget_def))
    span = norm.get("time_span", Period.TOTAL)
    days = norm.get("custom_days") if span == Period.CUSTOM else None
    import time

    token = int(time.time() * 1000)
    WidgetRegistry.update_many({
        d["id"]: {"time_span": span, "custom_days": days, "_timespan_token": token}
        for d in WidgetRegistry.get_all()
        if has_time_span(d) and d.get("id")
    })
    manager._last_state = None
    manager.refresh()


def fill_span_menu(menu, manager, widget, widget_def):
    """The period list of a widget: its periods, then zoom, new period, apply to all."""
    from .....ui.shared.span_menu import populate_span_menu

    widget_def = _latest(widget_def)
    from .....ui.shared.zoom_span import create_span_from_zoom, find_zoomed_chart

    zoomed = find_zoomed_chart(widget)

    def on_zoom_span(chart=zoomed):
        code = create_span_from_zoom(chart, manager._config_manager, parent=widget)
        if code is not None:
            manager._update_span_bulk(widget_def["id"], {"time_span": code})

    populate_span_menu(
        menu,
        widget_def.get("time_span", Period.TOTAL),
        widget_def.get("custom_days", None),
        lambda v, d=None: set_span(manager, widget_def, v, d),
        manager._config_manager,
        on_manage_callback=manager._open_time_span_settings,
        on_zoom_callback=on_zoom_span if zoomed is not None else None,
    )
    if sum(1 for d in WidgetRegistry.get_all() if has_time_span(d)) > 1:
        all_act = menu.addAction(tr("Apply to all widgets"))
        all_act.setIcon(get_svg_icon("copy", size=14))
        all_act.triggered.connect(lambda _=False: apply_span_to_all(manager, widget_def))


def choose_decks(manager, widget, widget_def):
    """The deck picker of a widget (with its filter field)."""
    widget_def = _latest(widget_def)
    current = widget_def.get("deck_ids", None)
    if current is None and "deck_id" in widget_def:
        old = widget_def["deck_id"]
        current = None if old in (None, 0, "0") else [int(old)]
    dialog = DeckMultiSelectDialog(current, parent=widget)
    if dialog.exec():
        WidgetRegistry.update_settings_bulk(widget_def["id"], {
            "deck_ids": dialog.selected_deck_ids,
            "deck_id": None,
        })
        manager.refresh()


def themed_menu(parent, manager):
    """A menu in the pinned widgets' theme (the right-click menu, the period list)."""
    menu = StyledMenu(parent)
    menu.setProperty("deepdivestats_theme_context", "pinned")
    menu.setProperty("deepdivestats_ignore_forced_dark_theme", True)
    try:
        cfg = (manager._config_manager.config or {}) if getattr(manager, "_config_manager", None) else {}
        menu.setProperty("deepdivestats_config_override", dict(cfg))
        menu._apply_theme_style()
    except Exception:
        log_swallowed()
    return menu


# -- The labels ---------------------------------------------------------------------------

class _Chip(QToolButton):
    """Text and a small arrow on a light pill, in the title's color."""

    def __init__(self, card, title, tooltip):
        super().__init__(card)
        self._title = title
        self.setObjectName("dd_card_chip")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setToolTip(tooltip)
        self.setAutoRaise(True)
        self.setStyleSheet("QToolButton { background: transparent; border: none; }")
        self.label = ""
        self.hide()

    def chip_font(self):
        font = QFont(self._title.font())
        px = self._title.fontInfo().pixelSize()
        font.setPixelSize(max(8, int(round(px * 0.95))))
        font.setBold(False)
        font.setWeight(QFont.Weight.Medium)
        font.setCapitalization(QFont.Capitalization.MixedCase)
        return font

    def fit(self):
        fm = QFontMetrics(self.chip_font())
        h = max(16, min(self._title.height(), fm.height() + 6))
        self.setFixedSize(fm.horizontalAdvance(self.label) + 2 * _PAD + _CHEVRON + 3, h)

    def paintEvent(self, _event):
        try:
            color = QColor(self._title.palette().color(QPalette.ColorRole.WindowText))
        except RuntimeError:
            return
        if not color.isValid():
            color = QColor(150, 150, 150)
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            back = QColor(color)
            back.setAlpha(48 if self.underMouse() else 22)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(back)
            r = self.height() / 2.0
            p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), r, r)
            text = QColor(color)
            text.setAlpha(255 if self.underMouse() else 205)
            p.setFont(self.chip_font())
            p.setPen(text)
            text_rect = QRectF(_PAD, 0, self.width() - 2 * _PAD - _CHEVRON - 3, self.height())
            p.drawText(text_rect, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self.label)
            pen = QPen(text, 1.3)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            cx = self.width() - _PAD - _CHEVRON / 2.0
            cy = self.height() / 2.0 + 0.5
            p.drawPolyline([QPointF(cx - 3, cy - 1.5), QPointF(cx, cy + 1.5), QPointF(cx + 3, cy - 1.5)])
        finally:
            p.end()

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)


class _CardChips(QObject):
    """The two labels of a card, put in its title row right after the title (the row's
    layout makes room for them: the title elides, the header stats fold into their icon)."""

    def __init__(self, manager, card, title):
        super().__init__(card)
        self.manager = manager
        self.card = card
        self.title = title
        self.widget_def = None
        row = title.parentWidget()
        lay = row.layout() if row is not None else None
        self.span = _Chip(row or card, title, tr("Time Span"))
        self.deck = _Chip(row or card, title, tr("Select Decks..."))
        if isinstance(lay, QBoxLayout) and lay.indexOf(title) >= 0:
            at = lay.indexOf(title) + 1
            lay.insertSpacing(at, _GAP - lay.spacing() if lay.spacing() < _GAP else 0)
            lay.insertWidget(at + 1, self.span, 0, Qt.AlignmentFlag.AlignVCenter)
            lay.insertWidget(at + 2, self.deck, 0, Qt.AlignmentFlag.AlignVCenter)
        self.span.clicked.connect(self._open_spans)
        self.deck.clicked.connect(self._open_decks)
        title.installEventFilter(self)

    def set_def(self, widget_def):
        self.widget_def = widget_def
        self.span.label = span_text(self.manager, widget_def) if has_time_span(widget_def) else ""
        self.deck.label = deck_text(self.manager, widget_def)
        self._refit()

    def eventFilter(self, obj, event):
        # The pinned zoom changes the title's font: the labels follow it.
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.Show, QEvent.Type.Hide):
            QTimer.singleShot(0, self._refit)
        return False

    def _refit(self):
        try:
            wanted = labels_enabled(self.manager) and not self.title.isHidden() and self.title.text().strip()
            for chip in (self.span, self.deck):
                if chip.label and wanted:
                    chip.fit()
                    chip.show()
                    chip.update()
                else:
                    chip.hide()
        except RuntimeError:
            pass

    def _menu_at(self, chip, menu):
        """Above the label when the screen has room there (the menu then covers the title
        row and the cards above, not the chart), else under it."""
        below = chip.mapToGlobal(QPoint(0, chip.height() + 2))
        try:
            h = menu.sizeHint().height()
            top = chip.mapToGlobal(QPoint(0, 0)).y() - h - 2
            screen = chip.screen().availableGeometry() if chip.screen() is not None else None
            if screen is not None and top >= screen.top():
                return QPoint(below.x(), top)
        except RuntimeError:
            pass
        return below

    def _open_decks(self):
        if self.widget_def is not None:
            choose_decks(self.manager, self.card, self.widget_def)

    def _open_spans(self):
        if self.widget_def is None:
            return
        menu = themed_menu(self.card, self.manager)
        fill_span_menu(menu, self.manager, self.card, self.widget_def)
        menu.addSeparator()
        hide = menu.addAction(tr("Hide these labels"))
        hide.triggered.connect(lambda _=False: hide_card_labels(self.manager))
        menu.exec(self._menu_at(self.span, menu))



def labels_enabled(manager):
    """The labels can be turned off in Settings > Pinned Widgets."""
    try:
        return bool((manager._config_manager.config or {}).get(Config.PINNED_CARD_LABELS, True))
    except Exception:
        return True


def _set_labels(manager, on):
    try:
        manager._config_manager.set_value(Config.PINNED_CARD_LABELS, bool(on))
    except Exception:
        log_swallowed()
    refresh_card_labels(manager)


def hide_card_labels(manager):
    """Turn the labels off, with a note saying where they come back (and Undo)."""
    _set_labels(manager, False)
    try:
        from .undo_toast import show_undo_toast

        show_undo_toast(tr("Labels hidden. Settings > Pinned Widgets shows them again."),
                        lambda: _set_labels(manager, True))
    except Exception:
        log_swallowed()


def refresh_card_labels(manager):
    """Show or hide the labels of every chart on screen (after the setting changed)."""
    for widget in list((getattr(manager, "_active_widgets", None) or {}).values()):
        chips = getattr(widget, "_dd_card_chips", None)
        if chips is not None:
            chips._refit()


def attach_card_chips(manager, card, widget_def):
    """Add or update the period and deck labels of a pinned chart."""
    if card is None or not isinstance(widget_def, dict):
        return
    try:
        chips = getattr(card, "_dd_card_chips", None)
        if chips is None:
            title = next((l for l in card.findChildren(QWidget) if l.objectName() in _TITLE_NAMES), None)
            if title is None:
                return
            chips = _CardChips(manager, card, title)
            card._dd_card_chips = chips
        chips.set_def(widget_def)
    except RuntimeError:
        pass
    except Exception:
        log_swallowed()
