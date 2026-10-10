# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations

from typing import TYPE_CHECKING

from aqt.qt import QColor, QColorDialog, QHBoxLayout, QLabel, QPushButton, Qt, QWidget

from ... import COLOR_DEFAULTS
from ...theme.icons import get_svg_icon
from .....qss import set_qss
from ....logic.logger import log_swallowed

if TYPE_CHECKING:
    from ..dialogs.tabs_config_dialog import DetailedStatsConfigDialog


def save_global_config(dialog: "DetailedStatsConfigDialog", key: str, value) -> None:
    if key in COLOR_DEFAULTS and hasattr(dialog, "_set_data_color_value"):
        dialog._set_data_color_value(key, value)
    else:
        dialog.parent_dialog.addon_config.config[key] = value

    if key in COLOR_DEFAULTS:
        try:
            dialog.parent_dialog.addon_config.write_config()
        except Exception:
            log_swallowed()

    dialog._refresh_live_data_colors(source=f"config:{key}")
    dialog.parent_dialog.update_dashboard_visibility()

    for k, btn in dialog._reset_buttons.items():
        if k == key or k.startswith(f"{key}_"):
            update_reset_button_visibility(dialog, key, btn)


def make_color_button(
    dialog: "DetailedStatsConfigDialog", config_key: str, unique_suffix: str = ""
) -> QWidget:
    container = QWidget()
    lay = QHBoxLayout(container)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(6)

    baseline_hex = dialog._get_data_color_baseline().get(config_key, "#888888")
    if hasattr(dialog, "_get_data_color_current"):
        current_hex = dialog._get_data_color_current(config_key)
    else:
        current_hex = dialog.parent_dialog.addon_config.config.get(config_key, baseline_hex)
    storage_key = f"{config_key}{unique_suffix}"

    btn = QPushButton(parent=container)
    btn.setFixedSize(28, 22)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setToolTip("Click to pick color")
    set_qss(btn, 
        f"background-color: {current_hex}; border: 1px solid rgba(128,128,128,0.45); border-radius: 4px;"
    )
    dialog._color_buttons[storage_key] = btn

    hex_lbl = QLabel(current_hex.upper(), parent=container)
    set_qss(hex_lbl, "font-size: 10px; font-family: monospace; background: transparent;")
    dialog._hex_labels[storage_key] = hex_lbl

    btn_reset = QPushButton(parent=container)
    btn_reset.setIcon(get_svg_icon("rotate-ccw", size=13))
    btn_reset.setFixedSize(22, 22)
    btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_reset.setToolTip("Reset to preset value")
    set_qss(btn_reset, 
        "QPushButton { background: transparent; border: none; } "
        "QPushButton:hover { background: rgba(128,128,128,0.18); border-radius: 4px; }"
    )
    dialog._reset_buttons[storage_key] = btn_reset
    update_reset_button_visibility(dialog, config_key, btn_reset)

    def _apply_hex(hex_val: str) -> None:
        set_qss(btn, 
            f"background-color: {hex_val}; border: 1px solid rgba(128,128,128,0.45); border-radius: 4px;"
        )
        hex_lbl.setText(hex_val.upper())
        for k, color_btn in dialog._color_buttons.items():
            if k.startswith(config_key) and color_btn is not btn:
                set_qss(color_btn, 
                    f"background-color: {hex_val}; border: 1px solid rgba(128,128,128,0.45); border-radius: 4px;"
                )
        for k, label in dialog._hex_labels.items():
            if k.startswith(config_key) and label is not hex_lbl:
                label.setText(hex_val.upper())

    def on_click() -> None:
        if hasattr(dialog, "_get_data_color_current"):
            cur_hex = dialog._get_data_color_current(config_key)
        else:
            cur_hex = dialog.parent_dialog.addon_config.config.get(config_key, baseline_hex)
        cur = QColor(cur_hex)
        chosen = QColorDialog.getColor(cur, dialog, "Pick Color")
        if not chosen.isValid():
            return
        new_hex = chosen.name()
        _apply_hex(new_hex)
        save_global_config(dialog, config_key, new_hex)

    def on_reset() -> None:
        default_hex = dialog._get_data_color_baseline().get(config_key, "#888888")
        _apply_hex(default_hex)
        save_global_config(dialog, config_key, default_hex)

    btn.clicked.connect(on_click)
    btn_reset.clicked.connect(on_reset)

    lay.addWidget(btn)
    lay.addWidget(hex_lbl)
    lay.addWidget(btn_reset)
    lay.addStretch()

    return container


def update_reset_button_visibility(
    dialog: "DetailedStatsConfigDialog", config_key: str, btn_reset: QPushButton
) -> None:
    default = str(dialog._get_data_color_baseline().get(config_key, "")).lower()
    if hasattr(dialog, "_get_data_color_current"):
        current = str(dialog._get_data_color_current(config_key)).lower()
    else:
        current = str(dialog.parent_dialog.addon_config.config.get(config_key, default)).lower()
    btn_reset.setVisible(current != default and bool(default))


