# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QAction

from ..shared.menu import StyledMenu
from ...logic.logger import log_swallowed


def show_header_menu(dialog, pos, table, header):
    menu = StyledMenu(dialog)

    col_map = {
        "Time": "show_time",
        "Reviews": "show_reviews",
        "Retention": "show_retention",
        "Ret. Young": "show_retention_young",
        "Ret. Mature": "show_retention_mature",
        "Buttons": "show_buttons_dist",
        "Avg Time": "show_avg_time",
        "Longest Streak": "show_longest_streak",
        "Streak": "show_streak",
        "Active Days": "show_active_days",
        "Forecast": "show_forecast",
    }

    for col_idx in range(table.columnCount()):
        item = table.horizontalHeaderItem(col_idx)
        if not item:
            continue
        name = item.text()

        if name in col_map:
            key = col_map[name]
            is_visible = not table.isColumnHidden(col_idx)

            action = QAction(name, dialog)
            action.setCheckable(True)
            action.setChecked(is_visible)

            def toggle(checked, col=col_idx, k=key):
                table.setColumnHidden(col, not checked)
                if hasattr(dialog, "get_tabs_config") and hasattr(dialog, "save_tabs_config"):
                    tabs_data = dialog.get_tabs_config()
                    enabled_idx = [i for i, t in enumerate(tabs_data) if t.get("enabled", True)]
                    # The deck view reads its columns from the first span, the time view from the current one.
                    if getattr(dialog, "view_mode", "time") == "time":
                        current_idx = dialog.tab_widget.currentIndex()
                    else:
                        current_idx = 0
                    if 0 <= current_idx < len(enabled_idx):
                        tabs_data[enabled_idx[current_idx]][k] = checked
                        dialog.save_tabs_config(tabs_data)

            action.triggered.connect(toggle)
            menu.addAction(action)

    try:
        from ..time_spans import add_time_span_actions

        add_time_span_actions(menu, dialog)
    except Exception:
        log_swallowed()

    menu.exec(header.mapToGlobal(pos))
