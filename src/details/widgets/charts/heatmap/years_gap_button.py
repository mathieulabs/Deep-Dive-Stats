# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The button next to YRS that takes out (or puts back) the space between the years.

Shown only in the all years view. The button shows the current state, also when the
option changes from the settings (HeatmapWidget.on_years_no_gap_changed).
"""
from aqt.qt import QPushButton, Qt

from ....ui.theme.icons import get_svg_icon
from .....i18n import tr
from .....qss import set_qss


def make_years_gap_button(parent, chart, style, color_hex, on_toggle):
    """on_toggle(no_gap): save the option and apply it to chart."""
    btn = QPushButton(parent=parent)
    btn.setObjectName("heatmap_years_gap_btn")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn.setFlat(True)
    set_qss(btn, style)
    btn.setFixedSize(20, 20)

    def refresh(color=None):
        if color:
            btn.setProperty("years_gap_icon_color", color)
        col = btn.property("years_gap_icon_color") or color_hex
        no_gap = bool(getattr(chart, "years_no_gap", False))
        # The icon shows what a click does: spread the rows (no space now) or close them up.
        btn.setIcon(get_svg_icon("unfold-vertical" if no_gap else "fold-vertical", size=14, color=col))
        btn.setToolTip(tr("Add space between the years") if no_gap else tr("Remove the space between the years"))

    btn.clicked.connect(lambda _checked=False: on_toggle(not bool(getattr(chart, "years_no_gap", False))))
    chart.on_years_no_gap_changed = refresh
    btn.refresh_years_gap = refresh
    refresh()
    return btn
