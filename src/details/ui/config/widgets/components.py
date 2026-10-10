# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import (
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QSizePolicy,
    Qt,
    QWidget,
)


class SettingsSlider(QWidget):
    """A standardized slider component with a manual input spinbox."""

    def __init__(
        self,
        label_text,
        value,
        min_val,
        max_val,
        interval=1,
        suffix="",
        parent=None,
        label_min_width=100,
    ):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.label = QLabel(label_text)
        self.label.setMinimumWidth(label_min_width)
        layout.addWidget(self.label)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(min_val, max_val)
        self.slider.setValue(value)
        self.slider.setSingleStep(interval)
        self.slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.slider)

        self.spin = QSpinBox()
        self.spin.setRange(min_val, max_val)
        self.spin.setValue(value)
        self.spin.setSingleStep(interval)
        self.spin.setSuffix(suffix)
        self.spin.setFixedWidth(70)
        self.spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.spin)

        self.slider.valueChanged.connect(self.spin.setValue)
        self.spin.valueChanged.connect(self.slider.setValue)

    def value(self):
        return self.slider.value()

    def setValue(self, val):
        self.slider.blockSignals(True)
        self.spin.blockSignals(True)
        self.slider.setValue(val)
        self.spin.setValue(val)
        self.slider.blockSignals(False)
        self.spin.blockSignals(False)

