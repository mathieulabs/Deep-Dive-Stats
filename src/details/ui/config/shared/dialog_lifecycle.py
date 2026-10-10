# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations

import copy

from aqt.qt import QApplication
from aqt.theme import theme_manager

from ...theme import get_settings_dialog_style
from ... import Config
from .....qss import set_qss
from ....logic.logger import log_swallowed


def restore_initial_config_snapshot(dialog) -> None:
    """Rollback config/tabs snapshots and re-apply runtime UI state."""
    if getattr(dialog, "_cancel_restored", False):
        return

    cfg = dialog.parent_dialog.addon_config.config
    cfg.clear()
    cfg.update(copy.deepcopy(dialog._initial_config_snapshot))
    dialog.tabs_data = copy.deepcopy(dialog._initial_tabs_data_snapshot)
    dialog.load_tabs_list()
    if dialog.tabs_list.count() > 0:
        dialog.tabs_list.setCurrentRow(0)

    try:
        dialog.parent_dialog.addon_config.write_config()
    except Exception:
        log_swallowed()

    try:
        dialog._apply_pinned_theme_runtime(source="settings_cancel_restore")
    except Exception:
        log_swallowed()

    try:
        val = bool(dialog.parent_dialog.addon_config.config.get(Config.DETAILS_SIDE_VIEW, False))
        dialog.parent_dialog.side_view = val
        from ...dialog.lifecycle import apply_split_orientation, effective_side_view

        apply_split_orientation(dialog.parent_dialog, effective_side_view(dialog.parent_dialog))
    except Exception:
        log_swallowed()

    try:
        dialog._refresh_live_data_colors(
            source="settings_cancel_restore",
            emit_theme_runtime=False,
        )
    except Exception:
        log_swallowed()
    try:
        if hasattr(dialog.parent_dialog, "update_dashboard_visibility"):
            dialog.parent_dialog.update_dashboard_visibility()
        if hasattr(dialog.parent_dialog, "refresh_styles"):
            dialog.parent_dialog.refresh_styles()
    except Exception:
        log_swallowed()
    try:
        dialog._refresh_binning_live()
    except Exception:
        log_swallowed()


def _retint_theme_dependent_controls(dialog) -> None:
    """Controls whose style or icon was built from the theme palette when the
    dialog opened. Redo them so a theme picked in Settings shows everywhere."""
    for name in (
        "_update_theme_base_mode_button_styles",
        "_update_pinned_theme_base_mode_button_styles",
        "_backdrop_sync_controls",
    ):
        fn = getattr(dialog, name, None)
        if callable(fn):
            try:
                fn()
            except Exception:
                log_swallowed()
    try:
        from ...theme.icons import get_svg_icon
        from ...theme.palette import get_theme_palette
        from ...theme.theme_mode import get_theme_effective_is_dark

        conf = dialog.parent_dialog.addon_config.config
        is_dark = get_theme_effective_is_dark(conf)
        icon_col = (get_theme_palette(conf) or {}).get("text_secondary") or (
            "#a1a1aa" if is_dark else "#71717a"
        )
    except Exception:
        return
    buttons = []
    for attr in ("_reset_buttons", "_theme_reset_buttons", "_pinned_theme_reset_buttons"):
        found = getattr(dialog, attr, None)
        if isinstance(found, dict):
            buttons.extend(found.values())
    extra = getattr(dialog, "binning_scale_reset_btn", None)
    if extra is not None:
        buttons.append(extra)
    for btn in buttons:
        try:
            btn.setIcon(get_svg_icon("rotate-ccw", color=icon_col, size=13))
        except Exception:
            log_swallowed()


def refresh_dialog_styles(dialog) -> None:
    is_dark = theme_manager.get_night_mode()
    set_qss(dialog, get_settings_dialog_style(is_dark, dialog.parent_dialog.addon_config.config))
    _retint_theme_dependent_controls(dialog)


def load_tabs_list(dialog) -> None:
    dialog.tabs_list.clear()
    for tab in dialog.tabs_data:
        title = tab.get("title", "Untitled")
        if not tab.get("enabled", True):
            title = f"(Archived) {title}"
        dialog.tabs_list.addItem(title)
    if dialog.tabs_data:
        dialog.tabs_list.setCurrentRow(0)


def find_visible_settings_dialog(dialog_cls):
    for widget in QApplication.topLevelWidgets():
        try:
            if isinstance(widget, dialog_cls) and widget.isVisible():
                return widget
        except Exception:
            continue
    return None

