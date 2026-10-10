# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations

from typing import TYPE_CHECKING

from aqt.qt import QInputDialog, QMessageBox

from ... import Config
from ... import ThemePalettes
from .preset_helpers import (
    get_custom_theme_presets,
    is_builtin_theme_preset_key,
    is_custom_theme_preset_selected,
)
from .preset_mutations import (
    delete_selected_custom_theme_preset,
    save_new_custom_theme_preset,
    update_selected_custom_theme_preset,
)

if TYPE_CHECKING:
    from ..dialogs.tabs_config_dialog import DetailedStatsConfigDialog


def update_theme_preset_action_buttons(dialog: "DetailedStatsConfigDialog") -> None:
    if not hasattr(dialog, "delete_theme_preset_btn"):
        return
    conf = dialog.parent_dialog.addon_config.config
    current_key = conf.get(Config.THEME_PRESET, ThemePalettes.NATIVE)
    is_custom_selected = is_custom_theme_preset_selected(
        current_key=current_key,
        custom_presets=get_custom_theme_presets(conf),
    )
    if hasattr(dialog, "update_theme_preset_btn"):
        dialog.update_theme_preset_btn.setEnabled(is_custom_selected)
        dialog.update_theme_preset_btn.setVisible(is_custom_selected)
    dialog.delete_theme_preset_btn.setEnabled(is_custom_selected)
    dialog.delete_theme_preset_btn.setVisible(is_custom_selected)


def on_update_theme_preset(dialog: "DetailedStatsConfigDialog") -> None:
    conf = dialog.parent_dialog.addon_config.config
    current_key = conf.get(Config.THEME_PRESET, ThemePalettes.NATIVE)
    custom_presets = get_custom_theme_presets(conf)
    if is_builtin_theme_preset_key(current_key) or current_key not in custom_presets:
        QMessageBox.information(
            dialog,
            "Update Preset",
            "Select a custom preset to update. Built-in presets cannot be modified.",
        )
        return

    effective = dialog._get_current_theme_effective_palette()
    effective_mode = dialog._get_current_theme_effective_base_mode()
    update_selected_custom_theme_preset(
        conf,
        current_key,
        custom_presets,
        palette=effective,
        base_mode=effective_mode,
        data_colors=dialog._get_current_data_colors(),
    )
    dialog._rebuild_theme_cards(current_preset=current_key)
    dialog._refresh_theme_color_controls()
    dialog._refresh_pinned_theme_controls()
    dialog._update_theme_preset_action_buttons()
    dialog._apply_theme_change()


def on_save_theme_preset(dialog: "DetailedStatsConfigDialog") -> None:
    effective = dialog._get_current_theme_effective_palette()
    effective_mode = dialog._get_current_theme_effective_base_mode()
    name, ok = QInputDialog.getText(dialog, "Save Theme Preset", "Preset name:")
    if not ok:
        return
    name = name.strip()
    if not name:
        QMessageBox.warning(dialog, "Invalid Name", "Preset name cannot be empty.")
        return

    conf = dialog.parent_dialog.addon_config.config
    custom_presets = conf.get(Config.THEME_CUSTOM_PRESETS, {})
    if not isinstance(custom_presets, dict):
        custom_presets = {}
        conf[Config.THEME_CUSTOM_PRESETS] = custom_presets

    key = save_new_custom_theme_preset(
        conf,
        custom_presets,
        name=name,
        palette=effective,
        base_mode=effective_mode,
        data_colors=dialog._get_current_data_colors(),
    )
    dialog._rebuild_theme_cards(current_preset=key)
    dialog._refresh_theme_color_controls()
    dialog._refresh_pinned_theme_controls()
    dialog._update_theme_preset_action_buttons()
    dialog._apply_theme_change()


def on_delete_theme_preset(dialog: "DetailedStatsConfigDialog") -> None:
    conf = dialog.parent_dialog.addon_config.config
    current_key = conf.get(Config.THEME_PRESET, ThemePalettes.NATIVE)
    custom_presets = get_custom_theme_presets(conf)
    if is_builtin_theme_preset_key(current_key) or current_key not in custom_presets:
        QMessageBox.information(dialog, "Delete Preset", "Select a custom preset to delete.")
        return

    entry = custom_presets.get(current_key, {})
    preset_name = str(entry.get("name", current_key))
    msg = f"Delete theme preset '{preset_name}'?"
    if QMessageBox.question(dialog, "Delete Preset", msg) != QMessageBox.StandardButton.Yes:
        return

    delete_selected_custom_theme_preset(conf, custom_presets, current_key)
    dialog._rebuild_theme_cards(current_preset=ThemePalettes.NATIVE)
    dialog._refresh_theme_color_controls()
    dialog._refresh_pinned_theme_controls()
    dialog._update_theme_preset_action_buttons()
    dialog._apply_theme_change()

