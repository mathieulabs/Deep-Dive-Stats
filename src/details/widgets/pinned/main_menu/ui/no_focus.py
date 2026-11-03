# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Nothing on the main screen's pinned area takes the keyboard focus.

A click on a pinned widget's button or check box gave it the focus. When that widget then
went away (removed, rebuilt by the guided tour or a refresh), Qt moved the focus on as a Tab
press would, to the next widget: Anki's page, whose first "+" (the first deck's) then showed
as selected. The pinned area is used with the mouse only, so its widgets never take the
focus and the page keeps it.

The rule is set on every widget of the area when it is first shown (polished) and again on
each show of the area, for the widgets that were made elsewhere and moved in."""

from aqt.qt import QApplication, QEvent, QObject, Qt, QWidget

from .....logic.logger import log_swallowed

_AREA = "pinned_overlay"


def _in_area(w):
    p = w
    while p is not None:
        if p.objectName() == _AREA:
            return True
        p = p.parentWidget()
    return False


class _NoFocusOnPolish(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Polish and isinstance(obj, QWidget):
            try:
                if obj.focusPolicy() != Qt.FocusPolicy.NoFocus and _in_area(obj):
                    obj.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            except RuntimeError:
                pass
        return False


_filter = [None]


def install_no_focus():
    """Once per Anki session."""
    if _filter[0] is not None:
        return
    try:
        _filter[0] = _NoFocusOnPolish()
        QApplication.instance().installEventFilter(_filter[0])
    except Exception:
        _filter[0] = None
        log_swallowed()


def clear_focus_policies(area):
    """Every widget of the area: no focus (the ones moved in after their first show)."""
    if area is None:
        return
    try:
        for w in area.findChildren(QWidget):
            if w.focusPolicy() != Qt.FocusPolicy.NoFocus:
                w.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        focused = QApplication.focusWidget()
        if focused is not None and area.isAncestorOf(focused):
            # It has the focus already: hand it to the page now, as a click would (not as
            # a Tab press, which selects the page's first element).
            page = area.parentWidget()
            if page is not None:
                page.setFocus(Qt.FocusReason.OtherFocusReason)
    except RuntimeError:
        pass
