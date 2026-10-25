# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations

from typing import TYPE_CHECKING

from aqt.qt import QColor, QColorDialog, QHBoxLayout, QLabel, QPushButton, Qt, QWidget
from aqt.theme import theme_manager

from ... import Config
from ... import COLOR_DEFAULTS, ThemePalettes
from ...theme.icons import get_svg_icon
from .preset_helpers import get_custom_theme_presets, is_theme_color_overridden
from .preset_helpers import resolve_theme_preset_palette
from .preset_mutations import select_theme_preset
from .ui_helpers import (
    apply_theme_card_filter,
    build_theme_card_defs,
    make_theme_card,
    rebuild_theme_cards_grid,
    set_theme_color_button_hex,
)
from .....qss import set_qss

if TYPE_CHECKING:
    from ..dialogs.tabs_config_dialog import DetailedStatsConfigDialog


def update_theme_reset_button_visibility(
    dialog: "DetailedStatsConfigDialog", color_key: str
) -> None:
    btn_reset = dialog._theme_reset_buttons.get(color_key)
    if not btn_reset:
        return
    conf = dialog.parent_dialog.addon_config.config
    custom_map = conf.get(Config.THEME_CUSTOM_COLORS, {})
    base_palette = dialog._get_current_theme_base_palette()
    base_hex = base_palette.get(color_key, ThemePalettes.CHARCOAL_PALETTE.get(color_key, "#000000"))
    cur_hex = dialog._get_current_theme_effective_palette().get(color_key, base_hex)
    changed = is_theme_color_overridden(color_key, custom_map, base_hex, cur_hex)
    btn_reset.setVisible(changed)


def refresh_theme_base_mode_control(dialog: "DetailedStatsConfigDialog") -> None:
    if not hasattr(dialog, "theme_base_mode_buttons"):
        return
    effective_mode = dialog._get_current_theme_effective_base_mode()
    preset_key = dialog.parent_dialog.addon_config.config.get(Config.THEME_PRESET, ThemePalettes.NATIVE)

    for mode, btn in dialog.theme_base_mode_buttons.items():
        btn.blockSignals(True)
        btn.setChecked(mode == effective_mode)
        btn.blockSignals(False)

    is_native_selected = preset_key == ThemePalettes.NATIVE
    for btn in dialog.theme_base_mode_buttons.values():
        btn.setEnabled(not is_native_selected)
    dialog.theme_base_mode_label.setEnabled(not is_native_selected)
    tooltip = (
        "Controls graph adaptation mode (line/border/text contrast) for this preset."
        if not is_native_selected
        else "Anki Native always follows Anki light/dark mode."
    )
    for btn in dialog.theme_base_mode_buttons.values():
        btn.setToolTip(tooltip)
    dialog._update_theme_base_mode_button_styles()


def refresh_theme_color_controls(dialog: "DetailedStatsConfigDialog") -> None:
    dialog._refresh_theme_base_mode_control()
    effective = dialog._get_current_theme_effective_palette()
    for key, _label in dialog._theme_keys:
        val = effective.get(key, ThemePalettes.CHARCOAL_PALETTE.get(key, "#000000"))
        set_theme_color_button_hex(
            dialog._theme_color_buttons.get(key),
            dialog._theme_hex_labels.get(key),
            val,
        )
        update_theme_reset_button_visibility(dialog, key)


def make_theme_color_control(
    dialog: "DetailedStatsConfigDialog", color_key: str
) -> QWidget:
    container = QWidget()
    lay = QHBoxLayout(container)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(6)

    current_hex = dialog._get_current_theme_effective_palette().get(
        color_key, ThemePalettes.CHARCOAL_PALETTE.get(color_key, "#000000")
    )
    btn = QPushButton(parent=container)
    btn.setFixedSize(28, 22)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setToolTip("Click to pick color")
    dialog._theme_color_buttons[color_key] = btn

    hex_lbl = QLabel(current_hex.upper(), parent=container)
    set_qss(hex_lbl, "font-size: 10px; font-family: monospace; background: transparent;")
    dialog._theme_hex_labels[color_key] = hex_lbl

    btn_reset = QPushButton(parent=container)
    btn_reset.setIcon(get_svg_icon("rotate-ccw", size=13))
    btn_reset.setFixedSize(22, 22)
    btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_reset.setToolTip("Reset to preset value")
    set_qss(btn_reset,
        "QPushButton { background: transparent; border: none; } "
        "QPushButton:hover { background: rgba(128,128,128,0.18); border-radius: 4px; }"
    )
    dialog._theme_reset_buttons[color_key] = btn_reset

    def on_click() -> None:
        cur_hex = dialog._get_current_theme_effective_palette().get(
            color_key, ThemePalettes.CHARCOAL_PALETTE.get(color_key, "#000000")
        )
        chosen = QColorDialog.getColor(QColor(cur_hex), dialog, f"Pick {color_key}")
        if not chosen.isValid():
            return
        dialog._set_theme_override_color(color_key, chosen.name())

    def on_reset() -> None:
        base_hex = dialog._get_current_theme_base_palette().get(
            color_key, ThemePalettes.CHARCOAL_PALETTE.get(color_key, "#000000")
        )
        dialog._set_theme_override_color(color_key, base_hex)

    btn.clicked.connect(on_click)
    btn_reset.clicked.connect(on_reset)

    lay.addWidget(btn)
    lay.addWidget(hex_lbl)
    lay.addWidget(btn_reset)
    lay.addStretch()
    set_theme_color_button_hex(btn, hex_lbl, current_hex)
    update_theme_reset_button_visibility(dialog, color_key)
    return container


def rebuild_theme_cards(
    dialog: "DetailedStatsConfigDialog", current_preset: str | None = None
) -> None:
    conf = dialog.parent_dialog.addon_config.config
    if current_preset is None:
        current_preset = conf.get(Config.THEME_PRESET, ThemePalettes.NATIVE)
    all_defs = build_theme_card_defs(
        builtin_defs=dialog._builtin_theme_defs,
        custom_presets=get_custom_theme_presets(conf),
    )
    dialog._theme_card_widgets = rebuild_theme_cards_grid(
        grid=dialog.theme_cards_grid,
        card_container=dialog.theme_cards_container,
        current_preset=current_preset,
        card_defs=all_defs,
        make_card=dialog._make_theme_card,
        on_click=dialog.on_theme_card_clicked,
        columns=3,
    )
    state = getattr(dialog, "_theme_filter_state", None)
    if state is not None:
        apply_theme_card_filter(dialog.theme_cards_grid, dialog._theme_card_widgets, state, columns=3)


def make_theme_card_widget(
    dialog: "DetailedStatsConfigDialog",
    preset_key: str,
    preset_name: str,
    current_preset: str,
    on_click,
    parent_widget=None,
):
    conf = dialog.parent_dialog.addon_config.config
    palette = resolve_theme_preset_palette(
        preset_key=preset_key,
        custom_presets=get_custom_theme_presets(conf),
        is_night_mode=theme_manager.get_night_mode(),
    )
    return make_theme_card(
        preset_key=preset_key,
        preset_name=preset_name,
        current_preset=current_preset,
        palette=palette,
        on_click=on_click,
        parent_widget=parent_widget,
        is_custom=preset_key in get_custom_theme_presets(conf),
    )


def on_theme_card_clicked(dialog: "DetailedStatsConfigDialog", preset_key: str) -> None:
    conf = dialog.parent_dialog.addon_config.config
    select_theme_preset(conf, preset_key)
    custom_presets = get_custom_theme_presets(conf)
    entry = custom_presets.get(preset_key, {})
    if isinstance(entry, dict) and isinstance(entry.get("data_colors"), dict):
        dialog._apply_data_colors({**COLOR_DEFAULTS, **entry["data_colors"]})
    else:
        dialog._apply_data_colors(ThemePalettes.get_preset_data_colors(preset_key))
    rebuild_theme_cards(dialog, current_preset=preset_key)
    dialog._refresh_theme_color_controls()
    dialog._update_theme_preset_action_buttons()
    dialog._apply_theme_change()


