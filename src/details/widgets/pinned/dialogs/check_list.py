# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The filter field and the "Select all" / "Deselect all" button of the dialogs that list
check boxes (decks, views). The dialog keeps its rows in self._rows ({"label", "widget",
"check", ...}) and its button in self.bulk_btn."""

from .....i18n import tr


class CheckListMixin:
    def _filter_rows(self, text: str):
        t = (text or "").strip().lower()
        for r in self._rows:
            r["widget"].setVisible(bool(t in r["label"]) if t else True)
        self._update_bulk_button_state()

    def showEvent(self, event):
        super().showEvent(event)
        # The rows only report their state once the dialog is shown.
        self._update_bulk_button_state()

    def _shown_rows(self):
        # isHidden(), not isVisible(): before the dialog shows, every row is "not visible".
        return [r for r in self._rows if not r["widget"].isHidden()]

    def _set_bulk(self, next_action):
        self._bulk_next_action = next_action
        self.bulk_btn.setText(tr("Deselect all") if next_action == "deselect_all" else tr("Select all"))

    def _on_bulk_clicked(self):
        rows = self._shown_rows()
        if not rows:
            return
        check = self._bulk_next_action == "select_all"
        for r in rows:
            r["check"].setChecked(check)
        self._set_bulk("deselect_all" if check else "select_all")

    def _update_bulk_button_state(self, *_args):
        rows = self._shown_rows()
        self.bulk_btn.setEnabled(bool(rows))
        self._rows_changed()
        if not rows:
            self._set_bulk("select_all")
            return
        self._set_bulk("deselect_all" if all(r["check"].isChecked() for r in rows) else "select_all")

    def _rows_changed(self):
        """After a filter or a check: a dialog can update its other buttons here."""
