# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QAbstractItemView, QHeaderView, QTableWidget, Qt, QFont

from ...widgets import HTMLDelegate
from .zebra import apply_zebra


def _watch_multi_selection(dialog, table):
    """Open the merged Deep Dive when a drag or Shift selection made by the user ends on several rows.

    Selections the table makes by itself (restoring the window, refreshing rows) are ignored,
    so they never replace the deck Anki is on.
    """
    import time

    from aqt.qt import QApplication, QEvent, QObject, QTimer

    state = {"last_input": 0.0}

    class _InputWatcher(QObject):
        def eventFilter(self, obj, event):
            if event.type() in (
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonRelease,
                QEvent.Type.KeyPress,
                QEvent.Type.KeyRelease,
            ):
                state["last_input"] = time.monotonic()
            return False

    watcher = _InputWatcher(table)
    table.installEventFilter(watcher)
    table.viewport().installEventFilter(watcher)

    timer = QTimer(table)
    timer.setSingleShot(True)
    timer.setInterval(150)

    def _fire():
        if QApplication.mouseButtons() != Qt.MouseButton.NoButton:
            timer.start()
            return
        if time.monotonic() - state["last_input"] > 0.8:
            return
        from ..interactions.core import _open_selection_merged

        if getattr(dialog, "view_mode", None) == "time":
            _open_selection_merged(dialog, table)

    timer.timeout.connect(_fire)
    table.itemSelectionChanged.connect(timer.start)


def setup_table(
    dialog,
    table,
    show_time,
    show_reviews,
    show_retention,
    show_retention_young,
    show_retention_mature,
    show_avg_time,
    show_streak=False,
    show_longest_streak=False,
    show_buttons_dist=False,
    row_height=30,
    show_active_days=True,
    show_forecast=True,
    show_header_menu_fn=None,
):
    headers = ["Deck"]
    if show_time:
        headers.append("Time")
    if show_reviews:
        headers.append("Reviews")
    if show_retention:
        headers.append("Retention")
    if show_retention_young:
        headers.append("Ret. Young")
    if show_retention_mature:
        headers.append("Ret. Mature")
    if show_buttons_dist:
        headers.append("Buttons")
    if show_avg_time:
        headers.append("Avg Time")
    if show_longest_streak:
        headers.append("Longest Streak")
    if show_streak:
        headers.append("Streak")
    if show_active_days:
        headers.append("Active Days")
    if show_forecast:
        headers.append("Forecast")

    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)

    header = table.horizontalHeader()
    header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    if show_header_menu_fn is not None:
        header.customContextMenuRequested.connect(
            lambda pos: show_header_menu_fn(dialog, pos, table, header)
        )

    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
    header.resizeSection(0, 180)
    for i in range(1, len(headers)):
        header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
    from .fill_width import install_fill

    install_fill(table)

    header_font = QFont()
    header_font.setBold(True)
    header.setFont(header_font)

    table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.horizontalScrollBar().setSingleStep(15)
    table.verticalScrollBar().setSingleStep(15)
    apply_zebra(table)
    _watch_multi_selection(dialog, table)
    table.verticalHeader().setVisible(True)
    table.verticalHeader().setDefaultSectionSize(row_height)
    table.verticalHeader().setFixedWidth(15)
    table.setShowGrid(False)

    delegate = HTMLDelegate(table)
    table.setItemDelegate(delegate)
    table.setSortingEnabled(False)
    header.setSectionsClickable(True)
    header.sectionClicked.connect(lambda idx: dialog.on_header_clicked(table, idx))
