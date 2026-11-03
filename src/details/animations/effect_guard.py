# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Graphics effects (fades, shadows) must never be nested.

A widget with a QGraphicsEffect is drawn off screen, then onto its window. When one of its
children (or one of its parents) has an effect too, Qt paints the same surface with two
painters at once ("A paint device can only be painted by one painter at a time"), and the
next widget drawn can bring Anki down. Before giving a widget an effect, the code asks
effect_nested(); a fade then simply does not run (the widget shows at once), and a lasting
effect (a shadow) waits until the fade around it has ended.
"""

from aqt.qt import QWidget


def _ancestor_has_effect(widget):
    parent = widget.parentWidget()
    while parent is not None:
        if parent.graphicsEffect() is not None:
            return True
        if parent.isWindow():
            return False
        parent = parent.parentWidget()
    return False


def _descendant_has_effect(widget):
    for child in widget.findChildren(QWidget):
        if child.graphicsEffect() is not None:
            return True
    return False


def effect_nested(widget, *, check_children=True):
    """True when an effect on widget would sit inside, or around, another effect."""
    try:
        if widget is None:
            return False
        if _ancestor_has_effect(widget):
            return True
        return bool(check_children and _descendant_has_effect(widget))
    except RuntimeError:
        return True
