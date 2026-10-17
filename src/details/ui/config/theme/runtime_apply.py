# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations

from aqt.qt import QTimer

from .runtime_refresh import refresh_live_data_colors


def apply_theme_change(dialog) -> None:
    scroll = getattr(dialog, "colors_scroll", None)
    scroll_pos = scroll.verticalScrollBar().value() if scroll else 0
    dialog.parent_dialog.addon_config.write_config()
    # Theme/preset changes can replace many data color keys at once: reload the color config in all live charts and widgets now. The theme runtime signal is emitted by refresh_styles() below.
    refresh_live_data_colors(
        parent_dialog=dialog.parent_dialog,
        addon_config=dialog.parent_dialog.addon_config,
        self_widget=dialog,
        source="theme_change",
        emit_theme_runtime=False,
    )
    if hasattr(dialog.parent_dialog, "update_dashboard_visibility"):
        dialog.parent_dialog.update_dashboard_visibility()
    dialog.parent_dialog.refresh_styles()
    # A settings dialog opened from the pinned menu has no Deep Dive window behind it, so its
    # refresh_styles() does nothing and the pinned widgets would only get the new data colors.
    # Broadcast the theme here when the host did not.
    from ....widgets.chart_utils.theme import sync_theme_manager_from_config, theme_already_synced

    live_conf = dialog.parent_dialog.addon_config.config
    if not theme_already_synced(live_conf):
        sync_theme_manager_from_config(live_conf, emit=True, source="theme_change")
    dialog.refresh_styles()
    if scroll:
        QTimer.singleShot(0, lambda: scroll.verticalScrollBar().setValue(scroll_pos))


def refresh_live_data_colors_runtime(dialog, source=None, emit_theme_runtime=True) -> None:
    refresh_live_data_colors(
        parent_dialog=dialog.parent_dialog,
        addon_config=dialog.parent_dialog.addon_config,
        self_widget=dialog,
        source=source,
        emit_theme_runtime=emit_theme_runtime,
    )


def apply_pinned_theme_runtime(dialog, source="pinned_theme_change") -> None:
    conf = dialog.parent_dialog.addon_config.config
    from ....widgets.chart_utils.theme import sync_theme_manager_from_config

    sync_theme_manager_from_config(conf, emit=True, source=source)

