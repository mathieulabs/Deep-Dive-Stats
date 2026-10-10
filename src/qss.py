# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""set_qss(): setStyleSheet() that skips identical sheets.

QWidget.setStyleSheet() re-polishes the whole subtree even when the sheet did
not change, and the theme is re-applied on every navigation.
"""


def set_qss(widget, sheet):
    if sheet is None:
        sheet = ""
    try:
        if widget.styleSheet() == sheet:
            return False
        widget.setStyleSheet(sheet)
        return True
    except RuntimeError:
        return False
