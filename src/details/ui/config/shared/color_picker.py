# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""A color picker that shows the color live while it is being chosen (the charts, the heatmap, the pinned
widgets and the Deep Dive window follow it), as the window backdrop's glow colors do."""

from aqt.qt import QColor, QColorDialog, QTimer

# a color dragged in the picker changes many times a second: applied at most this often (each apply repaints
# the pages, and some write the settings file)
_LIVE_MS = 70


def pick_color_live(parent, initial_hex, title, apply):
    """Open the picker on initial_hex. apply(hex) is called as the color changes, with the color chosen on OK,
    and with initial_hex again on Cancel when something was shown meanwhile. Returns the chosen hex, or None."""
    initial = QColor(initial_hex).name() if QColor(initial_hex).isValid() else "#000000"
    picker = QColorDialog(QColor(initial), parent)
    picker.setWindowTitle(title)
    state = {"pending": None, "shown": initial}
    timer = QTimer(picker)
    timer.setSingleShot(True)

    def flush():
        hex_ = state["pending"]
        state["pending"] = None
        if hex_ and hex_ != state["shown"]:
            state["shown"] = hex_
            apply(hex_)

    def changed(color):
        if color.isValid():
            state["pending"] = color.name()
            if not timer.isActive():
                timer.start(_LIVE_MS)

    timer.timeout.connect(flush)
    picker.currentColorChanged.connect(changed)
    accepted = picker.exec()
    timer.stop()
    if accepted:
        chosen = picker.selectedColor()
        hex_ = chosen.name() if chosen.isValid() else state["shown"]
        if hex_ != state["shown"]:
            apply(hex_)
        return hex_
    if state["shown"] != initial:
        apply(initial)
    return None
