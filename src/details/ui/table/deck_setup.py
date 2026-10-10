# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QAbstractItemView, QHeaderView, QTableWidget, Qt, QFont

from ...widgets import HTMLDelegate
from .zebra import apply_zebra


def setup_table_for_deck_view(
    dialog,
    table,
    show_time,
    show_reviews,
    show_retention,
    show_retention_young,
    show_retention_mature,
    show_avg_time,
    show_buttons_dist=False,
    show_streak=False,
    show_longest_streak=False,
    row_height=30,
    show_active_days=True,
    show_forecast=True,
    show_header_menu_fn=None,
):
    """Setup table for deck view (time ranges as rows)."""
    cols = ["Period"]
    if show_time:
        cols.append("Time")
    if show_reviews:
        cols.append("Reviews")
    if show_retention:
        cols.append("Retention")
    if show_retention_young:
        cols.append("Ret. Young")
    if show_retention_mature:
        cols.append("Ret. Mature")
    if show_buttons_dist:
        cols.append("Buttons")
    if show_avg_time:
        cols.append("Avg Time")
    if show_longest_streak:
        cols.append("Longest Streak")
    if show_streak:
        cols.append("Streak")
    if show_active_days:
        cols.append("Active Days")
    if show_forecast:
        cols.append("Forecast")

    table.setColumnCount(len(cols))
    table.setHorizontalHeaderLabels(cols)

    header = table.horizontalHeader()
    header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    if show_header_menu_fn is not None:
        header.customContextMenuRequested.connect(
            lambda pos: show_header_menu_fn(dialog, pos, table, header)
        )

    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
    header.resizeSection(0, 180)
    for i in range(1, len(cols)):
        header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
    from .fill_width import install_fill

    install_fill(table)

    header_font = QFont()
    header_font.setBold(True)
    header.setFont(header_font)

    table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.horizontalScrollBar().setSingleStep(15)
    table.verticalScrollBar().setSingleStep(15)
    apply_zebra(table)
    table.verticalHeader().setVisible(True)
    table.verticalHeader().setDefaultSectionSize(row_height)
    table.verticalHeader().setFixedWidth(15)
    table.setShowGrid(False)

    delegate = HTMLDelegate(table)
    table.setItemDelegate(delegate)
    table.setSortingEnabled(True)
