# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Table column headers: shown translated, found by their English name."""
from aqt.qt import Qt

from ....i18n import tr_name

HEADER_KEY_ROLE = Qt.ItemDataRole.UserRole


def set_header_labels(table, keys):
    """Column headers shown translated; each keeps its English name (header_key) for the code
    that finds a column by name (sorting, column menu, Buttons visual)."""
    table.setHorizontalHeaderLabels([tr_name(key) for key in keys])
    for col, key in enumerate(keys):
        item = table.horizontalHeaderItem(col)
        if item is not None:
            item.setData(HEADER_KEY_ROLE, key)


def header_key(item):
    """English name of a column header (see set_header_labels)."""
    if item is None:
        return ""
    key = item.data(HEADER_KEY_ROLE)
    return key if isinstance(key, str) and key else item.text()
