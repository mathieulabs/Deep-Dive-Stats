# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The dialogs that list check boxes (decks, views): a line of text, a filter field, the rows, and
"Select all" / "Deselect all", Cancel and Save. The dialog keeps its rows in self._rows ({"label",
"widget", "check", "value", "is_special"}) and answers Save in _on_save."""
from __future__ import annotations

from typing import Any

from aqt import mw
from aqt.qt import QCheckBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget, Qt

from .....i18n import tr
from .....qss import set_qss
from ....logic.logger import log_swallowed

_SCROLL_QSS = """
    QScrollBar:vertical { width: 6px; margin: 0px; }
    QScrollBar:horizontal { height: 6px; margin: 0px; }
    QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
        border-radius: 3px;
        min-height: 18px;
        min-width: 18px;
    }
    QScrollBar::add-line, QScrollBar::sub-line { width: 0px; height: 0px; }
    QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
"""


def parse_selection(values, token):
    """The ids of a saved selection as ints, plus `token` (deleted cards, the main menu) when it is there."""
    out: set[Any] = set()
    for v in values or ():
        if v == token:
            out.add(token)
        elif v is not None:
            try:
                out.add(int(v))
            except Exception:
                log_swallowed()
    return out


class CheckListDialog(QDialog):
    def __init__(self, parent, title, height, intro, bulk_name, default_all, current_set):
        super().__init__(parent or mw)
        self.setWindowTitle(title)
        self.resize(420, height)
        try:
            from ...chart_utils.theme import ThemeContext, settings_dialog_qss_for

            set_qss(self, settings_dialog_qss_for(parent, default=ThemeContext.PINNED))
        except Exception:
            log_swallowed()

        self._default_all = default_all
        self._current_set = current_set
        self._rows: list[dict[str, Any]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(QLabel(intro))

        self.filter_edit = QLineEdit(self)
        self.filter_edit.setPlaceholderText(tr("Filter decks..."))
        self.filter_edit.textChanged.connect(self._filter_rows)
        layout.addWidget(self.filter_edit)

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        set_qss(self.scroll, _SCROLL_QSS)
        self.scroll_content = QWidget(self.scroll)
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.scroll_content)
        layout.addWidget(self.scroll)

        btn_row = QWidget(self)
        btns = QHBoxLayout(btn_row)
        btns.setContentsMargins(0, 6, 0, 0)
        self.bulk_btn = QPushButton(tr("Select all"), self)
        self.bulk_btn.setObjectName(bulk_name)
        self._bulk_next_action = "select_all"
        self.bulk_btn.clicked.connect(self._on_bulk_clicked)
        btns.addWidget(self.bulk_btn)
        btns.addStretch()
        cancel = QPushButton(tr("Cancel"), self)
        cancel.clicked.connect(self.reject)
        self.save_btn = QPushButton(tr("Save"), self)
        self.save_btn.clicked.connect(self._on_save)
        btns.addWidget(cancel)
        btns.addWidget(self.save_btn)
        layout.addWidget(btn_row)

    def _add_row(self, label: str, value: Any, is_special: bool = False):
        row = QWidget(self.scroll_content)
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 2, 0, 2)
        h.setSpacing(10)
        cb = QCheckBox(row)
        cb.setChecked(self._default_all or (value in self._current_set))
        cb.stateChanged.connect(self._update_bulk_button_state)
        h.addWidget(cb)
        lab = QLabel(label, row)
        if is_special:
            set_qss(lab, "font-style: italic; opacity: 0.8;")
        h.addWidget(lab)
        h.addStretch()
        self.scroll_layout.addWidget(row)
        self._rows.append({"widget": row, "label": label.lower(), "value": value, "check": cb, "is_special": is_special})

    def _add_deck_rows(self):
        """A row per deck, by name, then the filter field focused."""
        try:
            decks = list(mw.col.decks.all_names_and_ids())
        except Exception:
            decks = []
        decks.sort(key=lambda d: d.name.lower())
        for d in decks:
            self._add_row(d.name, int(d.id))
        self._update_bulk_button_state()
        self.filter_edit.setFocus()

    def _on_save(self):
        self.accept()

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
