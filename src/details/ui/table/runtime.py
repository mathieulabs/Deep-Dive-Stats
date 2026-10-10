# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QTableWidget, Qt

from .. import Config
from .core import populate_table


def repopulate_current_table(dialog):
    tab_widget = getattr(dialog, "tab_widget", None)
    if not tab_widget:
        return
    current_idx = tab_widget.currentIndex()
    stats = getattr(dialog, "tab_stats", {}).get(current_idx)
    if not stats or "data" not in stats or "tree_data" not in stats["data"]:
        return
    table = tab_widget.currentWidget().findChild(QTableWidget)
    if not table:
        return
    populate_table(
        table=table,
        results=stats["data"]["results"],
        totals=stats["data"]["totals"],
        expanded_decks=dialog.expanded_decks,
        deck_colors=dialog.addon_config.config.get(Config.DECK_COLORS, {}),
        range_type=stats.get("range_type", "week"),
        show_time=stats.get("show_time", True),
        show_reviews=stats.get("show_reviews", True),
        show_retention=stats.get("show_retention", True),
        show_retention_young=stats.get("show_retention_young", True),
        show_retention_mature=stats.get("show_retention_mature", True),
        show_buttons_dist=stats.get("show_buttons_dist", True),
        show_avg_time=stats.get("show_avg_time", True),
        show_streak=stats.get("show_streak", False),
        show_longest_streak=stats.get("show_longest_streak", True),
        show_active_days=stats.get("show_active_days", True),
        show_forecast=stats.get("show_forecast", True),
        show_trends=dialog.trend_toggle.isChecked() if hasattr(dialog, "trend_toggle") else False,
        show_counts=stats.get("show_counts", False),
        show_buttons_visual=dialog.addon_config.config.get(Config.SHOW_BUTTONS_DIST_VISUAL, True),
        show_retention_sparkline=dialog.addon_config.config.get(Config.RETENTION_SPARKLINE, False),
        use_decimal=stats.get("use_decimal", False),
        hrs_unit=stats.get("hrs_unit", "hrs"),
        min_unit=stats.get("min_unit", "min"),
        tree_data=stats["data"]["tree_data"],
        bin_labels=stats["data"]["meta"]["bin_labels"],
        start_ms=stats["data"]["range_info"]["start_ms"],
        end_ms=stats["data"]["range_info"]["end_ms"],
        sort_col=dialog._sort_col,
        sort_order=dialog._sort_order,
        pin_top=True,
    )


def on_header_clicked(dialog, table, col_idx):
    if dialog._sort_col == col_idx:
        if dialog._sort_order == Qt.SortOrder.DescendingOrder:
            dialog._sort_order = Qt.SortOrder.AscendingOrder
        else:
            dialog._sort_col = None
            dialog._sort_order = Qt.SortOrder.DescendingOrder
    else:
        dialog._sort_col = col_idx
        dialog._sort_order = Qt.SortOrder.DescendingOrder
    header = table.horizontalHeader()
    if dialog._sort_col is not None:
        header.setSortIndicator(col_idx, dialog._sort_order)
        header.setSortIndicatorShown(True)
    else:
        header.setSortIndicatorShown(False)

    current_idx = dialog.tab_widget.currentIndex()
    if current_idx in dialog.tab_stats:
        stats = dialog.tab_stats[current_idx]
        if "data" in stats and "tree_data" in stats["data"]:
            populate_table(
                table=table,
                results=stats["data"]["results"],
                totals=stats["data"]["totals"],
                expanded_decks=dialog.expanded_decks,
                deck_colors=dialog.addon_config.config.get(Config.DECK_COLORS, {}),
                range_type=stats.get("range_type", "week"),
                show_time=stats.get("show_time", True),
                show_reviews=stats.get("show_reviews", True),
                show_retention=stats.get("show_retention", True),
                show_retention_young=stats.get("show_retention_young", True),
                show_retention_mature=stats.get("show_retention_mature", True),
                show_buttons_dist=stats.get("show_buttons_dist", True),
                show_avg_time=stats.get("show_avg_time", True),
                show_streak=stats.get("show_streak", False),
                show_longest_streak=stats.get("show_longest_streak", True),
                show_active_days=stats.get("show_active_days", True),
                show_forecast=stats.get("show_forecast", True),
                show_trends=dialog.trend_toggle.isChecked() if hasattr(dialog, "trend_toggle") else False,
                show_counts=stats.get("show_counts", False),
                show_buttons_visual=dialog.addon_config.config.get(Config.SHOW_BUTTONS_DIST_VISUAL, True),
                show_retention_sparkline=dialog.addon_config.config.get(Config.RETENTION_SPARKLINE, False),
                use_decimal=stats.get("use_decimal", False),
                hrs_unit=stats.get("hrs_unit", "hrs"),
                min_unit=stats.get("min_unit", "min"),
                tree_data=stats["data"]["tree_data"],
                bin_labels=stats["data"]["meta"]["bin_labels"],
                start_ms=stats["data"]["range_info"]["start_ms"],
                end_ms=stats["data"]["range_info"]["end_ms"],
                sort_col=dialog._sort_col,
                sort_order=dialog._sort_order,
                pin_top=True,
            )
