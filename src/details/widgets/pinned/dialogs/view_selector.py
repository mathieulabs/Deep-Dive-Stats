# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations

from typing import Any

from .....i18n import tr
from .check_list import CheckListDialog, parse_selection

MAIN_MENU_TOKEN = "main_menu"


class PinnedViewSelectorDialog(CheckListDialog):
    """Pick the views where a pinned widget is visible.

    - has a 'Main menu' row (MAIN_MENU_TOKEN)
    - with no current selection, everything starts checked
    """

    def __init__(self, current_selection: list[Any] | None, parent=None, title: str | None = None):
        super().__init__(parent, title or tr("Select View"), 520, tr("Choose where this pinned graph is visible."),
                         "pinned_view_bulk_btn", current_selection is None, parse_selection(current_selection, MAIN_MENU_TOKEN))
        self.selected_values: list[Any] = []
        self._add_row(tr("Main menu"), MAIN_MENU_TOKEN)
        self._add_deck_rows()

    def _on_save(self):
        # The rows hold the main menu token and the deck ids (ints already).
        self.selected_values = [r["value"] for r in self._rows if r["check"].isChecked()]
        self.accept()
