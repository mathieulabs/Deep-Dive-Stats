# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import Qt

from ... import Config
from ....widgets.chart_utils.theme import get_theme_colors
from ...theme.icons import get_svg_icon
from ....logic.logger import log_swallowed


def show_and_animate(manager):
    if hasattr(manager.dialog, "layout_toggle_container"):
        manager.dialog.layout_toggle_container.setVisible(True)
    if hasattr(manager.dialog, "deck_select_btn"):
        manager.dialog.deck_select_btn.setVisible(True)
        manager.dialog.span_select_btn.setVisible(True)

    # Always keep container visible so handle stays accessible.
    was_hidden = not manager.dialog.expanded_container.isVisible()
    if was_hidden:
        manager.dialog.expanded_container.setVisible(True)
        manager.dialog.opacity_effect.setOpacity(0.0)
        try:
            manager.dialog.fade_anim.finished.disconnect()
        except Exception:
            log_swallowed()

        def _remove_fade_effect():
            try:
                manager.dialog.expanded_container.setGraphicsEffect(None)
            except Exception:
                log_swallowed()

        manager.dialog.fade_anim.finished.connect(_remove_fade_effect)
        manager.dialog.fade_anim.start()
    else:
        manager.dialog.opacity_effect.setOpacity(1.0)

    # apply_layout_state in dialog handles 0-size if layout_state == 0.
    manager.dialog.apply_layout_state(animated=False)

    if hasattr(manager.dialog, "expanded_title"):
        manager.dialog.expanded_title.setCursor(Qt.CursorShape.ArrowCursor)
        manager.dialog.expanded_title.mousePressEvent = None

    manager.dialog.expanded_container.setVisible(True)
    try:
        from ...details_dialog.table_drawer import sync

        sync(manager.dialog)
    except Exception:
        log_swallowed()


def toggle_stats_visibility(manager):
    """Toggle the visibility of the stats section (StatCardsContainer)."""
    is_collapsed = manager.addon_config.config.get(Config.DEEP_DIVE_STATS_COLLAPSED, False)
    new_state = not is_collapsed

    manager.addon_config.config[Config.DEEP_DIVE_STATS_COLLAPSED] = new_state
    manager.addon_config.write_config()

    if hasattr(manager.dialog, "stats_collapse_btn"):
        t_colors = get_theme_colors(manager.dialog)
        text_col = t_colors.get("text_secondary", t_colors.get("text"))
        icon_hex = text_col.name() if hasattr(text_col, "name") else None
        manager.dialog.stats_collapse_btn.setIcon(
            get_svg_icon("chevron-right" if new_state else "chevron-down", color=icon_hex)
        )

    if not manager.dialog.stats_container:
        return

    manager.dialog.stats_container.setVisible(not new_state)
    try:
        from ..layout_parts.fill_height import install as _fill

        _fill(manager)
    except Exception:
        log_swallowed()

    for idx in range(manager.dialog.expanded_chart_area.count()):
        item = manager.dialog.expanded_chart_area.itemAt(idx)
        if item and item.widget() and item.widget().objectName() == "stats_spacer":
            spacer = item.widget()
            spacer.setVisible(not new_state)
            if not new_state:
                spacer.setFixedHeight(15)
            else:
                spacer.setFixedHeight(0)
            break


