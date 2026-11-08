# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import re

from aqt.qt import QButtonGroup, QCheckBox, QHBoxLayout, QRadioButton, QSize, QSizePolicy, QWidget
from ...logic.logger import log_swallowed

_COMPACT_UNITS = (
    (re.compile(r"(\d+)\s*months?\b", re.I), r"\1m"),
    (re.compile(r"(\d+)\s*mo\b", re.I), r"\1m"),
    (re.compile(r"(\d+)\s*years?\b", re.I), r"\1y"),
    (re.compile(r"(\d+)\s*weeks?\b", re.I), r"\1w"),
    (re.compile(r"(\d+)\s*days?\b", re.I), r"\1d"),
)


def _compact_text(text):
    out = text
    for rx, repl in _COMPACT_UNITS:
        out = rx.sub(repl, out)
    return out


class _AdaptiveRadioContainer(QWidget):
    """Radio row shown as one button with the choice ("1m", with a chevron) that opens a menu
    of the choices, as the period labels and the "Breakdown" button: the same look at every
    width. A row of a single choice keeps its pill (short label when narrow)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._full = []
        self._compact = []
        self._mode = "full"  # "full", "compact" or "collapsed"
        self._collapsed = None
        self._card = None  # the chart's card, watched for its resizes (see _cap)

    def register(self, radios, setup_button=None):
        self._radios_list = list(radios)
        self._full = [r.text() for r in self._radios_list]
        self._compact = [_compact_text(t) for t in self._full]
        # The one button of the collapsed row, styled as the pills.
        btn = QRadioButton("", parent=self)
        btn.setAutoExclusive(False)
        if callable(setup_button):
            setup_button(btn)
        btn.setChecked(True)
        btn.hide()
        btn.clicked.connect(self._open_menu)
        from .menu_chevron import attach_chevron

        attach_chevron(btn)
        if self.layout() is not None:
            self.layout().addWidget(btn)
        self._collapsed = btn
        for r in self._radios_list:
            r.toggled.connect(lambda _on: self._sync_collapsed_text())
        self._sync_collapsed_text()
        if len(self._radios_list) > 1:
            self._set_mode("collapsed")

    def _current(self):
        for i, r in enumerate(self._radios_list):
            if r.isChecked():
                return i
        return 0

    def _sync_collapsed_text(self):
        if self._collapsed is None or not self._compact:
            return
        from .menu_chevron import place_chevron, with_room

        self._collapsed.setText(with_room(self._compact[self._current()]))
        place_chevron(self._collapsed)
        self._collapsed.setToolTip(self._full[self._current()])

    def _open_menu(self, _checked=False):
        btn = self._collapsed
        btn.setChecked(True)  # it stays "on": it shows the current choice
        try:
            from aqt.qt import QPoint

            from ...ui.shared.menu import StyledMenu

            menu = StyledMenu(btn)
            cur = self._current()
            for i, text in enumerate(self._full):
                act = menu.addAction(text)
                act.setCheckable(True)
                act.setChecked(i == cur)
                act.triggered.connect(lambda _c=False, k=i, m=menu: (m.close(), self._choose(k)))
            # Which buttons the row shows: the chart's settings (its range buttons).
            owner = self.parentWidget()
            while owner is not None and not callable(getattr(owner, "_open_settings", None)):
                owner = owner.parentWidget()
            if owner is not None:
                from ....i18n import tr

                menu.addSeparator()
                edit = menu.addAction(tr("Edit Buttons..."))
                edit.triggered.connect(lambda _c=False, o=owner: self._edit_buttons(o))
            menu.exec(btn.mapToGlobal(QPoint(0, btn.height())))
        except Exception:
            log_swallowed()

    @staticmethod
    def _edit_buttons(owner):
        """The chart's settings, scrolled to its Range Buttons box."""
        try:
            from ...ui.config.dialogs.widget_settings import WidgetSettingsDialog

            WidgetSettingsDialog.focus_next = "range_btn"
        except Exception:
            log_swallowed()
        owner._open_settings()

    def _choose(self, idx):
        if 0 <= idx < len(self._radios_list) and idx != self._current():
            self._radios_list[idx].click()  # as a click on its pill: the same callback

    def _width_for(self, texts):
        total = 0
        lay = self.layout()
        for r, t in zip(self._radios_list, texts):
            fm = r.fontMetrics()
            extra = max(0, r.sizeHint().width() - fm.horizontalAdvance(r.text()))
            total += fm.horizontalAdvance(t) + extra
        if lay is not None and len(texts) > 1:
            total += lay.spacing() * (len(texts) - 1)
        return total

    def _collapsed_width(self):
        btn = self._collapsed
        if btn is None:
            return self._width_for(self._compact)
        fm = btn.fontMetrics()
        extra = max(0, btn.sizeHint().width() - fm.horizontalAdvance(btn.text()))
        from .menu_chevron import with_room

        longest = max((fm.horizontalAdvance(with_room(t)) for t in self._compact), default=0)
        return longest + extra

    def sizeHint(self):
        base = super().sizeHint()
        try:
            if self._folds():
                return QSize(self._collapsed_width(), base.height())
            return QSize(self._width_for(self._full), base.height())
        except Exception:
            return base

    def _folds(self):
        return self._collapsed is not None and len(getattr(self, "_radios_list", [])) > 1

    def minimumSizeHint(self):
        base = super().minimumSizeHint()
        try:
            return QSize(self._collapsed_width(), base.height())
        except Exception:
            return base

    def _set_mode(self, mode):
        if mode == self._mode:
            return
        self._mode = mode
        collapsed = mode == "collapsed"
        texts = self._compact if mode == "compact" else self._full
        for i, r in enumerate(self._radios_list):
            r.setText(texts[i])
            r.setToolTip(self._full[i] if mode == "compact" and texts[i] != self._full[i] else "")
            r.setVisible(not collapsed)
        if self._collapsed is not None:
            self._sync_collapsed_text()
            self._collapsed.setVisible(collapsed)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        try:
            if self._folds():
                self._set_mode("collapsed")
                self._cap()
                return
            w = self.width()
            if w >= self._width_for(self._full):
                self._set_mode("full")
            elif w >= self._width_for(self._compact) and self._compact != self._full:
                self._set_mode("compact")
            elif self._collapsed is not None and len(self._radios_list) > 1:
                self._set_mode("collapsed")
            else:
                self._set_mode("compact")
            self._cap()
        except Exception:
            log_swallowed()

    # Short or folded, the row keeps only the width it shows (else a gap before "1m" while
    # the title is cut). The cap comes off when the card changes size, so it can unfold.

    def _cap(self):
        if self._mode == "full":
            cap = 16777215
        elif self._mode == "compact":
            cap = self._width_for(self._compact)
        else:
            cap = self._collapsed_width()
        if self.maximumWidth() != cap:
            self.setMaximumWidth(cap)
        self._watch_card()

    def _watch_card(self):
        if self._card is not None:
            return
        w = self.parentWidget()
        while w is not None:
            if w.objectName() == "pinned_widget_card" or type(w).__name__ == "ResizableWrapper":
                break
            w = w.parentWidget()
        if w is None:
            w = self.window()
        if w is not None and w is not self:
            self._card = w
            w.installEventFilter(self)

    def eventFilter(self, obj, event):
        try:
            from aqt.qt import QEvent

            if obj is self._card and event.type() == QEvent.Type.Resize and self.maximumWidth() != 16777215:
                self.setMaximumWidth(16777215)
        except RuntimeError:
            pass
        return False


def create_checkbox(text, checked=True, parent=None, setup=None):
    checkbox = QCheckBox(text, parent=parent)
    checkbox.setChecked(checked)
    if callable(setup):
        setup(checkbox)
    return checkbox


def create_radio_group(
    options,
    default_idx,
    callback,
    parent=None,
    setup_button=None,
    setup_container=None,
    spacing=10,
):
    container = _AdaptiveRadioContainer(parent)
    # Never wider than its pills: given the spare width of a wide header (fullscreen), it
    # put a gap between them and the controls before them (Future Due's Backlog).
    container.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    # Spare width goes before the pills: otherwise each pill is stretched and its text sits at the left.
    layout.addStretch(1)

    button_group = QButtonGroup(container)

    for i, option in enumerate(options):
        radio = QRadioButton(option, parent=container)
        if callable(setup_button):
            setup_button(radio)
        layout.addWidget(radio)
        button_group.addButton(radio, i)

        if i == default_idx:
            radio.blockSignals(True)
            radio.setChecked(True)
            radio.blockSignals(False)

    container.register([button_group.button(i) for i in range(len(options))], setup_button=setup_button)

    if hasattr(button_group, "idClicked"):
        button_group.idClicked.connect(callback)
    else:
        button_group.buttonClicked.connect(lambda btn: callback(button_group.id(btn)))

    if callable(setup_container):
        setup_container(container)
    return container
