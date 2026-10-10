# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations

from typing import Any

from aqt import mw
from aqt.qt import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    Qt,
)
from .....qss import set_qss
from ....logic.logger import log_swallowed


DELETED_TOKEN = "deleted"


class DeckMultiSelectDialog(QDialog):
    """Pick the decks a pinned widget reads from.

    - has a 'Deleted cards' row (DELETED_TOKEN = "deleted")
    - current_deck_ids=None means all decks (adaptive)
    - saving with everything checked returns None
    - saving a subset returns a list of int ids and/or "deleted"
    """

    def __init__(self, current_deck_ids: list[Any] | None, parent=None):
        super().__init__(parent or mw)
        self.setWindowTitle("Select Decks")
        self.resize(420, 540)

        try:
            from ...chart_utils.theme import ThemeContext, settings_dialog_qss_for

            set_qss(self, settings_dialog_qss_for(parent, default=ThemeContext.PINNED))
        except Exception:
            log_swallowed()

        # None = all selected (default)
        self._default_all = current_deck_ids is None
        self._current_set: set[Any] = set()
        if current_deck_ids is not None:
            for v in current_deck_ids:
                if v == DELETED_TOKEN:
                    self._current_set.add(DELETED_TOKEN)
                elif v is not None:
                    try:
                        self._current_set.add(int(v))
                    except Exception:
                        log_swallowed()

        self._rows: list[dict[str, Any]] = []
        self.selected_deck_ids: list[Any] | None = current_deck_ids

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Choose which decks provide data for this graph."))

        self.filter_edit = QLineEdit(self)
        self.filter_edit.setPlaceholderText("Filter decks...")
        self.filter_edit.textChanged.connect(self._filter_rows)
        layout.addWidget(self.filter_edit)

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        set_qss(self.scroll, 
            """
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
        )
        self.scroll_content = QWidget(self.scroll)
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.scroll_content)
        layout.addWidget(self.scroll)

        btn_row = QWidget(self)
        btns = QHBoxLayout(btn_row)
        btns.setContentsMargins(0, 6, 0, 0)

        self.bulk_btn = QPushButton("Select all", self)
        self.bulk_btn.setObjectName("pinned_deck_bulk_btn")
        self._bulk_next_action = "select_all"
        self.bulk_btn.clicked.connect(self._on_bulk_clicked)
        btns.addWidget(self.bulk_btn)

        btns.addStretch()
        cancel = QPushButton("Cancel", self)
        cancel.clicked.connect(self.reject)
        self.save_btn = QPushButton("Save", self)
        self.save_btn.clicked.connect(self._on_save)
        btns.addWidget(cancel)
        btns.addWidget(self.save_btn)
        layout.addWidget(btn_row)

        self._populate()
        self.filter_edit.setFocus()

    def _populate(self):
        for i in reversed(range(self.scroll_layout.count())):
            w = self.scroll_layout.itemAt(i).widget()
            if w:
                w.deleteLater()
        self._rows = []

        def _add_row(label: str, value: Any, is_special: bool = False):
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
            self._rows.append({
                "widget": row,
                "label": label.lower(),
                "value": value,
                "check": cb,
                "is_special": is_special,
            })

        _add_row("Deleted / removed cards", DELETED_TOKEN, is_special=True)

        sep = QWidget(self.scroll_content)
        sep.setFixedHeight(1)
        set_qss(sep, "background: rgba(128,128,128,0.25);")
        self.scroll_layout.addWidget(sep)

        try:
            decks = list(mw.col.decks.all_names_and_ids())
        except Exception:
            decks = []
        decks.sort(key=lambda d: d.name.lower())

        for d in decks:
            _add_row(d.name, int(d.id))

        self._update_bulk_button_state()

    def _filter_rows(self, text: str):
        t = (text or "").strip().lower()
        for r in self._rows:
            visible = (t in r["label"]) if t else True
            r["widget"].setVisible(bool(visible))
        self._update_bulk_button_state()

    def showEvent(self, event):
        super().showEvent(event)
        self._update_bulk_button_state()

    def _on_bulk_clicked(self):
        visible_rows = [r for r in self._rows if not r["widget"].isHidden()]
        if not visible_rows:
            return
        if self._bulk_next_action == "select_all":
            for r in visible_rows:
                r["check"].setChecked(True)
            self._bulk_next_action = "deselect_all"
            self.bulk_btn.setText("Deselect all")
        else:
            for r in visible_rows:
                r["check"].setChecked(False)
            self._bulk_next_action = "select_all"
            self.bulk_btn.setText("Select all")

    def _update_bulk_button_state(self, *_args):
        visible_rows = [r for r in self._rows if not r["widget"].isHidden()]
        if not visible_rows:
            self._bulk_next_action = "select_all"
            self.bulk_btn.setText("Select all")
            self.bulk_btn.setEnabled(False)
            self.save_btn.setEnabled(False)
            return
        self.bulk_btn.setEnabled(True)
        all_checked = all(r["check"].isChecked() for r in visible_rows)
        any_checked = any(r["check"].isChecked() for r in self._rows)
        self.save_btn.setEnabled(any_checked)
        if all_checked:
            self._bulk_next_action = "deselect_all"
            self.bulk_btn.setText("Deselect all")
        else:
            self._bulk_next_action = "select_all"
            self.bulk_btn.setText("Select all")

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
