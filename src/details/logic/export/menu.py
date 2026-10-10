# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QAction

from ...ui.shared.menu import StyledMenu
from ...ui.theme.icons import get_svg_icon
from .csv import export_to_csv
from .visual import export_visual


def setup_export_menu(dialog):
    """Attach a drop-down menu to dialog.export_btn with all export options."""
    menu = StyledMenu(dialog)

    act = QAction("  Export Deep Dive", dialog)
    act.setIcon(get_svg_icon("bar-chart-2", size=16))
    act.triggered.connect(lambda: export_visual(dialog, "deep_dive"))
    menu.addAction(act)

    act = QAction("  Export Table + Dashboard", dialog)
    act.setIcon(get_svg_icon("grid", size=16))
    act.triggered.connect(lambda: export_visual(dialog, "table"))
    menu.addAction(act)

    act = QAction("  Export Full View", dialog)
    act.setIcon(get_svg_icon("image", size=16))
    act.triggered.connect(lambda: export_visual(dialog, "full"))
    menu.addAction(act)

    menu.addSeparator()

    act = QAction("  Export Data (CSV)", dialog)
    act.setIcon(get_svg_icon("file-text", size=16))
    act.triggered.connect(lambda: export_to_csv(dialog))
    menu.addAction(act)

    dialog.export_btn.setMenu(menu)

