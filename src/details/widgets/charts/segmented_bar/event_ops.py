# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QWidget


def show_event_impl(widget, event):
    if not widget._animate_on_show:
        return QWidget.showEvent(widget, event)
    return QWidget.showEvent(widget, event)


def enter_event_impl(widget, event):
    text = widget.tooltip_text()
    if text:
        widget.setToolTip(text)
    QWidget.enterEvent(widget, event)


def mouse_double_click_event_impl(widget, event):
    if widget.doubleClicked:
        widget.doubleClicked()
    QWidget.mouseDoubleClickEvent(widget, event)
