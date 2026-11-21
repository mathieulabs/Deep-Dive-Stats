# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations

from typing import Any

from aqt.qt import QWidget

from .....i18n import tr
from .....qss import set_qss
from .check_list import CheckListDialog, parse_selection

DELETED_TOKEN = "deleted"


class DeckMultiSelectDialog(CheckListDialog):
    """Pick the decks a pinned widget reads from.

    - has a 'Deleted cards' row (DELETED_TOKEN = "deleted")
    - current_deck_ids=None means all decks (adaptive)
    - saving with everything checked returns None
    - saving a subset returns a list of int ids and/or "deleted"
    """

    def __init__(self, current_deck_ids: list[Any] | None, parent=None):
        super().__init__(parent, tr("Select Decks"), 540, tr("Choose which decks provide data for this graph."),
                         "pinned_deck_bulk_btn", current_deck_ids is None, parse_selection(current_deck_ids, DELETED_TOKEN))
        self.selected_deck_ids: list[Any] | None = current_deck_ids

        self._add_row(tr("Deleted / removed cards"), DELETED_TOKEN, is_special=True)
        sep = QWidget(self.scroll_content)
        sep.setFixedHeight(1)
        set_qss(sep, "background: rgba(128,128,128,0.25);")
        self.scroll_layout.addWidget(sep)
        self._add_deck_rows()

    def _rows_changed(self):
        self.save_btn.setEnabled(any(r["check"].isChecked() for r in self._rows))

    def _on_save(self):
        checked: list[Any] = [r["value"] for r in self._rows if r["check"].isChecked()]

        # If all deck rows and the deleted row are checked, None means "all, adaptive"
        all_deck_ids = {r["value"] for r in self._rows if not r["is_special"]}
        deleted_checked = DELETED_TOKEN in checked
        deck_ids_checked = {v for v in checked if v != DELETED_TOKEN}

        if deck_ids_checked == all_deck_ids and deleted_checked:
            # Everything checked: treat as "all" (adaptive, includes deleted)
            self.selected_deck_ids = None
        elif deck_ids_checked == all_deck_ids and not deleted_checked:
            # All standard decks checked, deleted not: adaptive (no deleted)
            self.selected_deck_ids = []
        else:
            result: list[Any] = []
            if deleted_checked:
                result.append(DELETED_TOKEN)
            for v in checked:
                if v != DELETED_TOKEN:
                    result.append(int(v))
            self.selected_deck_ids = result

        self.accept()
