# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QWidget


def mouse_double_click_event_impl(widget, event):
    if widget.doubleClicked:
        widget.doubleClicked()
    QWidget.mouseDoubleClickEvent(widget, event)
