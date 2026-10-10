# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations

from typing import TYPE_CHECKING

from ... import Config
from ....logic.logger import log_swallowed

if TYPE_CHECKING:
    from ..dialogs.tabs_config_dialog import DetailedStatsConfigDialog


def get_pinned_theme_mode_from_config(conf: dict | None) -> str:
    conf = conf if isinstance(conf, dict) else {}
    use_active = bool(conf.get(Config.PINNED_USE_ACTIVE_THEME, False))
    use_separate = bool(conf.get(Config.PINNED_USE_SEPARATE_THEME, False))
    if not use_active:
        return "native"
    if use_separate:
        return "separate"
    return "linked"


def set_pinned_theme_mode_in_config(dialog: "DetailedStatsConfigDialog", mode: str) -> None:
    mode = str(mode or "native").strip().lower()
    if mode == "linked":
        dialog.save_global_config(Config.PINNED_USE_ACTIVE_THEME, True)
        dialog.save_global_config(Config.PINNED_USE_SEPARATE_THEME, False)
        return
    if mode == "separate":
        dialog.save_global_config(Config.PINNED_USE_ACTIVE_THEME, True)
        dialog.save_global_config(Config.PINNED_USE_SEPARATE_THEME, True)
        return
    dialog.save_global_config(Config.PINNED_USE_ACTIVE_THEME, False)
    dialog.save_global_config(Config.PINNED_USE_SEPARATE_THEME, False)


def on_pinned_theme_mode_changed(dialog: "DetailedStatsConfigDialog") -> None:
    mode = dialog.pinned_theme_mode_combo.currentData()
    set_pinned_theme_mode_in_config(dialog, mode)
    try:
        dialog.parent_dialog.addon_config.write_config()
    except Exception:
        log_swallowed()
    update_pinned_theme_controls_state(dialog)
    if hasattr(dialog, "_refresh_data_color_controls"):
        dialog._refresh_data_color_controls()
    dialog._apply_pinned_theme_runtime(source="pinned_theme_mode")


def update_pinned_theme_controls_state(dialog: "DetailedStatsConfigDialog") -> None:
    if not hasattr(dialog, "pinned_theme_mode_combo"):
        return
    mode = str(dialog.pinned_theme_mode_combo.currentData() or "native")
    allow_pinned_custom = mode == "separate"
    sync_pinned_theme_tab_visibility(dialog, allow_pinned_custom)
    refresh_pinned_theme_mode_hint(dialog)
    if hasattr(dialog, "pinned_theme_cards_container"):
        dialog.pinned_theme_cards_container.setEnabled(allow_pinned_custom)
    if hasattr(dialog, "pinned_theme_base_mode_selector"):
        dialog.pinned_theme_base_mode_selector.setEnabled(allow_pinned_custom)
    if hasattr(dialog, "pinned_theme_base_mode_label"):
        dialog.pinned_theme_base_mode_label.setEnabled(allow_pinned_custom)
    if hasattr(dialog, "group_pinned_theme_manual"):
        dialog.group_pinned_theme_manual.setEnabled(allow_pinned_custom)


def refresh_pinned_theme_mode_hint(dialog: "DetailedStatsConfigDialog") -> None:
    if not hasattr(dialog, "pinned_theme_mode_hint"):
        return
    mode = str(dialog.pinned_theme_mode_combo.currentData() or "native")
    if mode == "native":
        text = "Pinned widgets use Anki native colors (not Details theme colors)."
    elif mode == "linked":
        text = "Pinned widgets use the same theme as Details (same preset and same custom colors)."
    else:
        text = "Pinned widgets use an independent theme. Configure it in the 'Pinned' tab."
    dialog.pinned_theme_mode_hint.setText(text)


def sync_pinned_theme_tab_visibility(
    dialog: "DetailedStatsConfigDialog", show_pinned_tab: bool
) -> None:
    if not hasattr(dialog, "theme_tabs") or not hasattr(dialog, "pinned_theme_tab"):
        return
    idx = dialog.theme_tabs.indexOf(dialog.pinned_theme_tab)
    if show_pinned_tab and idx < 0:
        dialog.theme_tabs.addTab(dialog.pinned_theme_tab, "Pinned")
    elif (not show_pinned_tab) and idx >= 0:
        dialog.theme_tabs.removeTab(idx)

    # Keep UI simple: hide tab bar when only "Details" is available.
    try:
        dialog.theme_tabs.tabBar().setVisible(dialog.theme_tabs.count() > 1)
    except Exception:
        log_swallowed()
    if dialog.theme_tabs.currentIndex() < 0 and dialog.theme_tabs.count() > 0:
        dialog.theme_tabs.setCurrentIndex(0)

