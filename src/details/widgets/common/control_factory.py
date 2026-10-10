# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import re

from aqt.qt import QButtonGroup, QCheckBox, QHBoxLayout, QRadioButton, QSize, QWidget
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
    """Radio row that switches to short labels ("3 months" -> "3m") when the
    header is too narrow, instead of letting the labels get clipped."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._full = []
        self._compact = []
        self._is_compact = False

    def register(self, radios):
        self._radios_list = list(radios)
        self._full = [r.text() for r in self._radios_list]
        self._compact = [_compact_text(t) for t in self._full]

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

    def sizeHint(self):
        base = super().sizeHint()
        try:
            return QSize(self._width_for(self._full), base.height())
        except Exception:
            return base

    def minimumSizeHint(self):
        base = super().minimumSizeHint()
        try:
            return QSize(self._width_for(self._compact), base.height())
        except Exception:
            return base

    def _set_compact(self, compact):
        if compact == self._is_compact or self._compact == self._full:
            return
        self._is_compact = compact
        texts = self._compact if compact else self._full
        for r, t in zip(self._radios_list, texts):
            r.setText(t)
            r.setToolTip(self._full[self._radios_list.index(r)] if compact else "")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        try:
            need_full = self._width_for(self._full if not self._is_compact else self._full)
            self._set_compact(self.width() < need_full)
        except Exception:
            log_swallowed()


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

    container.register([button_group.button(i) for i in range(len(options))])

    if hasattr(button_group, "idClicked"):
        button_group.idClicked.connect(callback)
    else:
        button_group.buttonClicked.connect(lambda btn: callback(button_group.id(btn)))

    if callable(setup_container):
        setup_container(container)
    return container
