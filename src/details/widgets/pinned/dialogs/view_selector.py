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
from .check_list import CheckListMixin
from ....logic.logger import log_swallowed
from .....i18n import tr


MAIN_MENU_TOKEN = "main_menu"


class PinnedViewSelectorDialog(CheckListMixin, QDialog):
    """Pick the views where a pinned widget is visible.

    - has a 'Main menu' row (MAIN_MENU_TOKEN)
    - with no current selection, everything starts checked
    """

    def __init__(self, current_selection: list[Any] | None, parent=None, title: str | None = None):
        super().__init__(parent or mw)
        self.setWindowTitle(title or tr("Select View"))
        self.resize(420, 520)

        try:
            from ...chart_utils.theme import ThemeContext, settings_dialog_qss_for

            set_qss(self, settings_dialog_qss_for(parent, default=ThemeContext.PINNED))
        except Exception:
            log_swallowed()

        self._rows: list[dict[str, Any]] = []
        self.selected_values: list[Any] = []

        self._default_all = current_selection is None
        self._current_set = set()
        if current_selection is not None:
            for v in current_selection:
                try:
                    if v == MAIN_MENU_TOKEN:
                        self._current_set.add(MAIN_MENU_TOKEN)
                    elif v is None:
                        continue
                    else:
                        self._current_set.add(int(v))
                except Exception:
                    continue

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        layout.addWidget(QLabel(tr("Choose where this pinned graph is visible.")))

        self.filter_edit = QLineEdit(self)
        self.filter_edit.setPlaceholderText(tr("Filter decks..."))
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

        self.bulk_btn = QPushButton(tr("Select all"), self)
        self.bulk_btn.setObjectName("pinned_view_bulk_btn")
        self._bulk_next_action = "select_all"  # or "deselect_all"
        self.bulk_btn.clicked.connect(self._on_bulk_clicked)
        btns.addWidget(self.bulk_btn)

        btns.addStretch()
        cancel = QPushButton(tr("Cancel"), self)
        cancel.clicked.connect(self.reject)
        save = QPushButton(tr("Save"), self)
        save.clicked.connect(self._on_save)
        btns.addWidget(cancel)
        btns.addWidget(save)
        layout.addWidget(btn_row)

        self._populate()
        self.filter_edit.setFocus()

    def _populate(self):
        for i in reversed(range(self.scroll_layout.count())):
            w = self.scroll_layout.itemAt(i).widget()
            if w:
                w.deleteLater()
        self._rows = []

        def _add_row(label: str, value: Any):
            row = QWidget(self.scroll_content)
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 2, 0, 2)
            h.setSpacing(10)

            cb = QCheckBox(row)
            cb.setChecked(self._default_all or (value in self._current_set))
            cb.stateChanged.connect(self._update_bulk_button_state)
            h.addWidget(cb)

            lab = QLabel(label, row)
            h.addWidget(lab)
            h.addStretch()

            self.scroll_layout.addWidget(row)
            self._rows.append(
                {
                    "widget": row,
                    "label": label.lower(),
                    "value": value,
                    "check": cb,
                }
            )

        _add_row(tr("Main menu"), MAIN_MENU_TOKEN)

        try:
            decks = list(mw.col.decks.all_names_and_ids())
        except Exception:
            decks = []
        decks.sort(key=lambda d: d.name.lower())

        for d in decks:
            _add_row(d.name, int(d.id))

        self._update_bulk_button_state()

    def _on_save(self):
        selected: list[Any] = []
        for r in self._rows:
            if r["check"].isChecked():
                selected.append(r["value"])

        normalized: list[Any] = []
        for v in selected:
            if v == MAIN_MENU_TOKEN:
                normalized.append(MAIN_MENU_TOKEN)
            else:
                try:
                    normalized.append(int(v))
                except Exception:
                    continue

        self.selected_values = normalized
        self.accept()
