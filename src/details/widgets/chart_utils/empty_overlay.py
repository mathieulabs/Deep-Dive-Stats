# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Centered "No data" label drawn over a chart that has nothing to show."""
from aqt.qt import QEvent, QLabel, QObject, Qt

NO_DATA_TEXT = "No data for this graph"


class _FillParent(QObject):
    """Keeps the label the size of its parent."""

    def __init__(self, label):
        super().__init__(label)
        self._label = label

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize:
            try:
                self._label.setGeometry(obj.rect())
            except RuntimeError:
                pass
        return False


def set_no_data(body, empty, text=NO_DATA_TEXT, style_label=None):
    """Show or hide the overlay on `body`. `style_label(label)` themes a new label."""
    if body is None:
        return
    lbl = getattr(body, "_dd_no_data_lbl", None)
    if not empty:
        if lbl is not None:
            lbl.hide()
        return
    if lbl is None:
        lbl = QLabel(text, body)
        lbl.setProperty("deepdivestats_theme_role", "empty_label")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        body.installEventFilter(_FillParent(lbl))
        body._dd_no_data_lbl = lbl
        if style_label is not None:
            style_label(lbl)
    lbl.setGeometry(body.rect())
    lbl.show()
    lbl.raise_()
