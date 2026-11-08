# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Future Due's "Breakdown" header button: one box that opens a small menu (Off / by type /
by result) instead of a box per breakdown, so the header stays short."""

from aqt.qt import QPoint

from .....i18n import tr
from ...common.menu_chevron import attach_chevron, place_chevron, with_room


def _label(mode):
    if mode == "type":
        return tr("Breakdown by Type")
    if mode == "result":
        return tr("Breakdown by Result")
    return tr("Breakdown")


def setup_breakdown_button(box, mode, on_change):
    """Turn a header box (made by the caller, in its own style) into the breakdown button.

    The box shows checked while a breakdown is on and names it; a click opens the menu
    instead of toggling. on_change(new mode or None) runs when the choice changes."""
    state = {"mode": mode}

    def refresh():
        box.blockSignals(True)
        box.setChecked(state["mode"] is not None)
        box.setText(with_room(_label(state["mode"])))  # it opens a menu: a chevron, as the folded range buttons
        place_chevron(box)
        box.blockSignals(False)

    def choose(kind, menu):
        menu.close()
        if kind == state["mode"]:
            return
        state["mode"] = kind
        refresh()
        on_change(kind)

    def open_menu(_checked=False):
        refresh()  # undo the box's own toggle: the menu decides
        from ....ui.shared.menu import StyledMenu

        menu = StyledMenu(box)
        for kind, text in ((None, tr("Off")), ("type", tr("Breakdown by Type")), ("result", tr("Breakdown by Result"))):
            act = menu.addAction(text)
            act.setCheckable(True)
            act.setChecked(kind == state["mode"])
            act.triggered.connect(lambda _c=False, k=kind, m=menu: choose(k, m))
        menu.exec(box.mapToGlobal(QPoint(0, box.height())))

    box.clicked.connect(open_menu)
    attach_chevron(box)
    refresh()
    return box
