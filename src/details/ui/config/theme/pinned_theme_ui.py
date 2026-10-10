# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations

from typing import TYPE_CHECKING

from aqt.qt import QColor, QColorDialog, QHBoxLayout, QLabel, QPushButton, Qt, QWidget

from ... import Config
from ... import ThemePalettes
from ...theme.icons import get_svg_icon
from .preset_helpers import get_custom_theme_presets
from .ui_helpers import clear_layout, set_theme_color_button_hex
from .....qss import set_qss

if TYPE_CHECKING:
    from ..dialogs.tabs_config_dialog import DetailedStatsConfigDialog


def set_pinned_theme_color_button_hex(
    dialog: "DetailedStatsConfigDialog", color_key: str, hex_val: str
) -> None:
    btn = dialog._pinned_theme_color_buttons.get(color_key)
    hl = dialog._pinned_theme_hex_labels.get(color_key)
    set_theme_color_button_hex(btn, hl, hex_val)


def update_pinned_theme_reset_button_visibility(
    dialog: "DetailedStatsConfigDialog", color_key: str
) -> None:
    btn_reset = dialog._pinned_theme_reset_buttons.get(color_key)
    if not btn_reset:
        return
    conf = dialog.parent_dialog.addon_config.config
    custom_map = conf.get(Config.PINNED_THEME_CUSTOM_COLORS, {})
    if not isinstance(custom_map, dict):
        custom_map = {}
    base_palette = dialog._get_current_pinned_theme_base_palette()
    base_hex = base_palette.get(color_key, ThemePalettes.CHARCOAL_PALETTE.get(color_key, "#000000"))
    cur_hex = dialog._get_current_pinned_theme_effective_palette().get(color_key, base_hex)
    changed = (color_key in custom_map) and (str(cur_hex).lower() != str(base_hex).lower())
    btn_reset.setVisible(changed)


def refresh_pinned_theme_color_controls(dialog: "DetailedStatsConfigDialog") -> None:
    effective = dialog._get_current_pinned_theme_effective_palette()
    for key, _label in dialog._theme_keys:
        val = effective.get(key, ThemePalettes.CHARCOAL_PALETTE.get(key, "#000000"))
        set_pinned_theme_color_button_hex(dialog, key, val)
        update_pinned_theme_reset_button_visibility(dialog, key)


def refresh_pinned_theme_base_mode_control(dialog: "DetailedStatsConfigDialog") -> None:
    if not hasattr(dialog, "pinned_theme_base_mode_buttons"):
        return
    effective_mode = dialog._get_current_pinned_theme_effective_base_mode()
    preset_key = dialog.parent_dialog.addon_config.config.get(Config.PINNED_THEME_PRESET, ThemePalettes.NATIVE)

    for mode, btn in dialog.pinned_theme_base_mode_buttons.items():
        btn.blockSignals(True)
        btn.setChecked(mode == effective_mode)
        btn.blockSignals(False)

    is_native_selected = preset_key == ThemePalettes.NATIVE
    for btn in dialog.pinned_theme_base_mode_buttons.values():
        btn.setEnabled(not is_native_selected)
    dialog.pinned_theme_base_mode_label.setEnabled(not is_native_selected)
    dialog._update_pinned_theme_base_mode_button_styles()


def make_pinned_theme_color_control(
    dialog: "DetailedStatsConfigDialog", color_key: str
) -> QWidget:
    container = QWidget()
    lay = QHBoxLayout(container)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(6)

    current_hex = dialog._get_current_pinned_theme_effective_palette().get(
        color_key, ThemePalettes.CHARCOAL_PALETTE.get(color_key, "#000000")
    )
    btn = QPushButton(parent=container)
    btn.setFixedSize(28, 22)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setToolTip("Click to pick color")
    dialog._pinned_theme_color_buttons[color_key] = btn

    hex_lbl = QLabel(current_hex.upper(), parent=container)
    set_qss(hex_lbl, "font-size: 10px; font-family: monospace; background: transparent;")
    dialog._pinned_theme_hex_labels[color_key] = hex_lbl

    btn_reset = QPushButton(parent=container)
    btn_reset.setIcon(get_svg_icon("rotate-ccw", size=13))
    btn_reset.setFixedSize(22, 22)
    btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_reset.setToolTip("Reset to preset value")
    set_qss(btn_reset, 
        "QPushButton { background: transparent; border: none; } "
        "QPushButton:hover { background: rgba(128,128,128,0.18); border-radius: 4px; }"
    )
    dialog._pinned_theme_reset_buttons[color_key] = btn_reset

    def on_click() -> None:
        cur_hex = dialog._get_current_pinned_theme_effective_palette().get(
            color_key, ThemePalettes.CHARCOAL_PALETTE.get(color_key, "#000000")
        )
        chosen = QColorDialog.getColor(QColor(cur_hex), dialog, f"Pick {color_key}")
        if not chosen.isValid():
            return
        dialog._set_pinned_theme_override_color(color_key, chosen.name())

    def on_reset() -> None:
        base_hex = dialog._get_current_pinned_theme_base_palette().get(
            color_key, ThemePalettes.CHARCOAL_PALETTE.get(color_key, "#000000")
        )
        dialog._set_pinned_theme_override_color(color_key, base_hex)

    btn.clicked.connect(on_click)
    btn_reset.clicked.connect(on_reset)

    lay.addWidget(btn)
    lay.addWidget(hex_lbl)
    lay.addWidget(btn_reset)
    lay.addStretch()
    set_pinned_theme_color_button_hex(dialog, color_key, current_hex)
    update_pinned_theme_reset_button_visibility(dialog, color_key)
    return container


def rebuild_pinned_theme_cards(
    dialog: "DetailedStatsConfigDialog", current_preset: str | None = None
) -> None:
    if not hasattr(dialog, "pinned_theme_cards_grid"):
        return
    conf = dialog.parent_dialog.addon_config.config
    if current_preset is None:
        current_preset = conf.get(Config.PINNED_THEME_PRESET, ThemePalettes.NATIVE)
    dialog._pinned_theme_card_widgets = {}
    clear_layout(dialog.pinned_theme_cards_grid)

    all_defs = list(dialog._builtin_theme_defs)
    for key, entry in get_custom_theme_presets(conf).items():
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", key))
        all_defs.append((key, name))
    for i, (preset_key, preset_name) in enumerate(all_defs):
        card = dialog._make_theme_card(
            preset_key,
            preset_name,
            current_preset,
            on_click=dialog.on_pinned_theme_card_clicked,
            parent_widget=dialog.pinned_theme_cards_container,
        )
        dialog._pinned_theme_card_widgets[preset_key] = card
        row, col = divmod(i, 3)
        dialog.pinned_theme_cards_grid.addWidget(card, row, col)


def on_pinned_theme_card_clicked(dialog: "DetailedStatsConfigDialog", preset_key: str) -> None:
    conf = dialog.parent_dialog.addon_config.config
    conf[Config.PINNED_THEME_PRESET] = preset_key
    conf[Config.PINNED_THEME_IS_CUSTOM] = False
    conf[Config.PINNED_THEME_CUSTOM_COLORS] = {}
    conf[Config.PINNED_THEME_CUSTOM_BASE_MODE] = None
    rebuild_pinned_theme_cards(dialog, current_preset=preset_key)
    dialog._refresh_pinned_theme_controls()
    if hasattr(dialog, "_refresh_data_color_controls"):
        dialog._refresh_data_color_controls()
    dialog._apply_theme_change()


