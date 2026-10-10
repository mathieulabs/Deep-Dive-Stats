# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QTableWidget, Qt


def filter_table(dialog, text):
    current_idx = dialog.tab_widget.currentIndex()
    if current_idx not in dialog.tab_stats:
        return

    tab = dialog.tab_widget.widget(current_idx)
    table = tab.findChild(QTableWidget)
    if not table:
        return

    text = text.lower()

    from .core import SortableTableWidgetItem

    pin_top = SortableTableWidgetItem.PIN_TOP
    start = 1 if pin_top else 0
    end = table.rowCount() if pin_top else table.rowCount() - 1

    def _set_hidden(row, hide):
        # Qt relayouts the header on every call, so only touch rows that change.
        if table.isRowHidden(row) != bool(hide):
            table.setRowHidden(row, bool(hide))

    table.setUpdatesEnabled(False)
    try:
        _filter_rows(dialog, table, text, start, end, _set_hidden)
    finally:
        table.setUpdatesEnabled(True)

    total_row = 0 if pin_top else table.rowCount() - 1
    _set_hidden(total_row, False)


def _filter_rows(dialog, table, text, start, end, _set_hidden):
    for row in range(start, end):
        item = table.item(row, 0)
        if not item:
            continue

        full_path = str(item.data(Qt.ItemDataRole.UserRole) or "")
        display_name = str(getattr(item, "sort_value", item.text())).lower()
        is_empty = item.data(Qt.ItemDataRole.UserRole + 1) is True

        if not text:
            should_hide = is_empty
            parts = full_path.split("::")
            ancestors = ["::".join(parts[:j]) for j in range(1, len(parts))]
            for ancestor in ancestors:
                if ancestor not in dialog.expanded_decks:
                    should_hide = True
                    break
            _set_hidden(row, should_hide)
        else:
            _set_hidden(row, not (text in full_path.lower() or text in display_name))
