# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QObject, QEvent

class NoWheelFilter(QObject):
    """
    An event filter that ignores wheel events.
    Prevents accidental value changes when scrolling through a settings dialog.
    """
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel:
            # Ignore the event so it doesn't reach the widget, 
            # allowing it to propagate up to the scroll area.
            event.ignore()
            return True
        return super().eventFilter(obj, event)

no_wheel_filter = NoWheelFilter()


def install_no_wheel_filters(root, widget_types):
    """Install the shared no-wheel event filter on matching children."""
    for widget in root.findChildren(widget_types):
        widget.installEventFilter(no_wheel_filter)

