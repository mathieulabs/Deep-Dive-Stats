# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations

from aqt.qt import QColor, QColorDialog
from .....qss import set_qss


def update_color_button(dialog) -> None:
    set_qss(dialog.color_btn,
        f"background-color: {dialog.current_color}; border: 1px solid #888; border-radius: 4px;"
    )
    if hasattr(dialog, "reset_color_btn"):
        baseline = (
            dialog._get_heatmap_color_baseline()
            if hasattr(dialog, "_get_heatmap_color_baseline")
            else "#3b82f6"
        )
        is_default = str(dialog.current_color).lower() == str(baseline).lower()
        dialog.reset_color_btn.setVisible(not is_default)


def select_color(dialog) -> None:
    color = QColorDialog.getColor(QColor(dialog.current_color), dialog, "Select Heatmap Color")
    if color.isValid():
        dialog.current_color = color.name()
        update_color_button(dialog)
        dialog.apply_live_changes()


def reset_color(dialog) -> None:
    if hasattr(dialog, "_get_heatmap_color_baseline"):
        dialog.current_color = dialog._get_heatmap_color_baseline()
    else:
        dialog.current_color = "#3b82f6"
    update_color_button(dialog)
    dialog.apply_live_changes()

