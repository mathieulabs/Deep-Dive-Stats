# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""One range radio button in a chart's settings: a preset, or a custom value."""
from __future__ import annotations

from aqt.qt import QComboBox, QHBoxLayout, QSpinBox, Qt, QWidget

_CUSTOM = "__custom__"


class _EnterSafeSpinBox(QSpinBox):
    """Enter confirms the number; it must not trigger the dialog's Save button."""

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.interpretText()
            event.accept()
            return
        super().keyPressEvent(event)


class RangeButtonRow(QWidget):
    """kind "days": value is an int number of days (-1 = all), custom is a day count.
    kind "fsrs": value is a mode string ("d200", "p85", "95_percent", "all"...)."""

    def __init__(self, kind, choices, value, parent=None):
        super().__init__(parent)
        self._kind = kind
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.combo = QComboBox(self)
        for data, label in choices:
            self.combo.addItem(label, data)
        self.combo.addItem("Custom...", _CUSTOM)
        lay.addWidget(self.combo, 1)
        # The row only holds a pending choice: the settings dialog reads it on Save, so its
        # controls must not trigger the live refresh (which rebuilds the Deep Dive charts).
        self.setProperty("noLiveUpdate", True)
        self.spin = _EnterSafeSpinBox(self)
        lay.addWidget(self.spin)
        self.unit = QComboBox(self)
        if kind == "fsrs":
            self.unit.addItem("days", "d")
            self.unit.addItem("%", "p")
            lay.addWidget(self.unit)
        self.combo.currentIndexChanged.connect(self._sync)
        self.unit.currentIndexChanged.connect(self._sync_range)
        self.set_value(value)

    def _sync_range(self, *_a):
        if self._kind == "fsrs" and self.unit.currentData() == "p":
            self.spin.setRange(1, 99)
            self.spin.setSuffix(" %")
        else:
            self.spin.setRange(1, 8999 if self._kind == "days" else 9999)
            self.spin.setSuffix(" day(s)")

    def _sync(self, *_a):
        custom = self.combo.currentData() == _CUSTOM
        self.spin.setVisible(custom)
        self.unit.setVisible(custom and self._kind == "fsrs")

    def currentData(self):
        data = self.combo.currentData()
        if data != _CUSTOM:
            return data
        if self._kind == "days":
            return int(self.spin.value())
        return f"{self.unit.currentData()}{int(self.spin.value())}"

    def set_value(self, value):
        idx = self.combo.findData(value)
        if idx >= 0:
            self.combo.setCurrentIndex(idx)
            self._sync_range()
            self._sync()
            return
        if self._kind == "days":
            n = int(value) if str(value).lstrip("-").isdigit() else 30
            self.unit.setCurrentIndex(0)
            self._sync_range()
            self.spin.setValue(max(1, n))
        else:
            from ....widgets.common.fsrs_filters import parse_fsrs_mode
            parsed = parse_fsrs_mode(value) or ("days", 30)
            self.unit.setCurrentIndex(1 if parsed[0] == "percent" else 0)
            self._sync_range()
            self.spin.setValue(max(1, parsed[1]))
        self.combo.setCurrentIndex(self.combo.findData(_CUSTOM))
        self._sync()
