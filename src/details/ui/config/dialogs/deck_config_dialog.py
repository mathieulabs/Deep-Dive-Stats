# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QWidget,
    QCheckBox,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QColorDialog,
    Qt,
    QColor,
    QSize,
    QSizePolicy,
)
from aqt import mw
from aqt.theme import theme_manager
from ... import ConfigManager, Config
from ...theme import get_settings_dialog_style
from ..shared import apply_standard_dialog_sizing, clamp_dialog_height
from .....qss import set_qss
from ...theme.icons import get_svg_icon

class _DeckNameLabel(QLabel):
    """Deck name that ends with "..." when the row is too narrow, so it never runs
    over the buttons before it. The full name is in the tooltip."""

    def __init__(self, name, parent=None):
        super().__init__(name, parent)
        self._full = name
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        shown = self.fontMetrics().elidedText(self._full, Qt.TextElideMode.ElideRight, max(0, self.width()))
        if shown != self.text():
            self.setText(shown)
        self.setToolTip(self._full if shown != self._full else "")


class DeckSettingsDialog(QDialog):
    def __init__(self, addon_config: ConfigManager, parent=None):
        super().__init__(parent or mw)
        self.setWindowTitle("Deck Options")

        apply_standard_dialog_sizing(self, min_width=500)
        self.addon_config = addon_config
        self.excluded_dids = set(self.addon_config.config.get(Config.EXCLUDED_DECKS, []))
        self.deck_colors = self.addon_config.config.get(Config.DECK_COLORS, {})

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Uncheck decks to exclude them from stats.\nClick the color box to set a custom color for the deck name."))

        self.filter_edit = QLineEdit(self)
        self.filter_edit.setPlaceholderText("Filter decks...")
        self.filter_edit.textChanged.connect(self.filter_decks)
        layout.addWidget(self.filter_edit)

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget(self.scroll)
        # Named like the other settings dialogs so the theme stylesheet makes it
        # transparent; otherwise Anki's own (dark) palette fills the list.
        self.scroll_content.setObjectName("scroll_content")
        self.scroll.viewport().setAutoFillBackground(False)
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.scroll_content)
        layout.addWidget(self.scroll)

        layout.addWidget(QLabel("Excluded dates (left out of the stats, for all decks or only some):"))
        self.dates_list = QListWidget(self)
        self.dates_list.setMaximumHeight(96)
        self.dates_list.setToolTip(
            "Reviews done on these days are ignored. Days start at your Anki rollover hour."
        )
        self.dates_list.itemDoubleClicked.connect(lambda _i: self._edit_date_rule())
        layout.addWidget(self.dates_list)
        for entry in (self.addon_config.config.get(Config.EXCLUDED_DATES, []) or []):
            self._add_rule_item(entry)
        rule_btns = QHBoxLayout()
        for text, slot in (("Add", self._add_date_rule), ("Edit", self._edit_date_rule), ("Remove", self._remove_date_rule)):
            btn = QPushButton(text, self)
            btn.clicked.connect(slot)
            rule_btns.addWidget(btn)
        rule_btns.addStretch(1)
        layout.addLayout(rule_btns)

        self.deck_rows = []
        self.populate_decks()

        self.bottom_area = QWidget(self)
        btns = QHBoxLayout(self.bottom_area)
        btns.setContentsMargins(0, 10, 0, 10)
        btns.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.clicked.connect(self.save)
        btns.addWidget(cancel)
        btns.addWidget(save)
        layout.addWidget(self.bottom_area)

        self.refresh_styles()

        from aqt.qt import QCoreApplication
        QCoreApplication.processEvents()

        content_h = self.scroll_content.sizeHint().height()
        # ScrollArea itself has a bit of overhead
        total_h = content_h + self.bottom_area.sizeHint().height() + 100

        final_h = clamp_dialog_height(self.maximumHeight(), total_h)
        self.resize(500, final_h)

    def populate_decks(self):
        for i in reversed(range(self.scroll_layout.count())):
            widget = self.scroll_layout.itemAt(i).widget()
            if widget: widget.deleteLater()
        self.deck_rows = []

        show_full_name = self.addon_config.config.get(Config.SHOW_FULL_DECK_NAME, False)

        self.add_config_row("Total", "total", allow_exclude=False)

        self.add_config_row("Deleted Cards", "deleted", allow_exclude=True)

        for deck in mw.col.decks.all():
            deck_name = deck['name']
            if not show_full_name and "::" in deck_name:
                deck_name = deck_name.split("::")[-1]
            self.add_config_row(deck_name, deck['id'], allow_exclude=True)

    def add_config_row(self, name, did, allow_exclude=True):
        row = QWidget(self.scroll_content)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 2, 0, 2)

        check = QCheckBox(parent=row)
        if allow_exclude:
            check.setChecked(did not in self.excluded_dids)
        else:
            check.setChecked(True)
            check.setEnabled(False)
        row_layout.addWidget(check)

        color_btn = QPushButton(parent=row)
        color_btn.setFixedSize(24, 24)
        current_color = self.deck_colors.get(str(did), "")
        self.update_color_btn(color_btn, current_color)
        color_btn.clicked.connect(lambda checked, b=color_btn, d=did: self.pick_color(b, d))
        row_layout.addWidget(color_btn)

        reset_btn = QPushButton(parent=row)
        reset_btn.setIcon(get_svg_icon("rotate-ccw", size=14))
        reset_btn.setIconSize(QSize(14, 14))
        reset_btn.setFixedSize(24, 24)
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # The dialog style gives buttons 6-7 px of padding, too much for 24 px.
        set_qss(reset_btn, "QPushButton { padding: 0px; min-height: 0px; min-width: 0px; }")
        reset_btn.setToolTip("Reset to default color")
        reset_btn.clicked.connect(lambda checked, b=color_btn, d=did: self.reset_color(b, d))
        row_layout.addWidget(reset_btn)

        label = _DeckNameLabel(name, parent=row)
        row_layout.addWidget(label, 1)

        self.scroll_layout.addWidget(row)

        self.deck_rows.append({
            "widget": row,
            "name": name.lower(),
            "did": did,
            "check": check,
            "label": label,
            "current_color": current_color
        })

    def update_color_btn(self, btn, color):
        if color:
            set_qss(btn, f"background-color: {color}; border: 1px solid #555;")
        else:
            set_qss(btn, "background-color: transparent; border: 1px solid #555;")

    def pick_color(self, btn, did):
        current = self.deck_colors.get(str(did))
        color = QColorDialog.getColor(QColor(current) if current else Qt.GlobalColor.white, self, "Pick Deck Color")
        if color.isValid():
            hex_color = color.name()
            self.deck_colors[str(did)] = hex_color
            self.update_color_btn(btn, hex_color)

            for row in self.deck_rows:
                if row['did'] == did:
                    set_qss(row['label'], f"color: {hex_color}")
                    row['current_color'] = hex_color
                    break

    def reset_color(self, btn, did):
        if str(did) in self.deck_colors:
            del self.deck_colors[str(did)]
        self.update_color_btn(btn, "")
        for row in self.deck_rows:
            if row['did'] == did:
                set_qss(row['label'], "")
                row['current_color'] = ""
                break

    def filter_decks(self, text):
        text = text.lower()
        for row in self.deck_rows:
            visible = text in row['name']
            row['widget'].setVisible(visible)

    @staticmethod
    def _rule_text(entry):
        if isinstance(entry, dict):
            n = len(entry.get("decks") or [])
            dates = entry.get("dates", "")
            return f"{dates}  ({n} deck{'s' if n != 1 else ''})" if n else f"{dates}  (all decks)"
        return f"{entry}  (all decks)"

    def _add_rule_item(self, entry):
        item = QListWidgetItem(self._rule_text(entry))
        item.setData(Qt.ItemDataRole.UserRole, entry)
        self.dates_list.addItem(item)

    @staticmethod
    def _valid_dates(text):
        from datetime import datetime
        first, _, last = text.strip().partition("..")
        try:
            datetime.strptime(first.strip(), "%Y-%m-%d")
            if last.strip():
                datetime.strptime(last.strip(), "%Y-%m-%d")
        except ValueError:
            return None
        return f"{first.strip()}..{last.strip()}" if last.strip() else first.strip()

    def _ask_rule(self, entry=None):
        """Ask for a date (or range) and the decks. Returns the new entry or None."""
        from aqt.utils import showWarning
        from ....widgets.pinned.dialogs.deck_multi_select import DeckMultiSelectDialog
        dates = entry.get("dates", "") if isinstance(entry, dict) else (entry or "")
        decks = list(entry.get("decks") or []) if isinstance(entry, dict) else []
        dlg = QDialog(self)
        dlg.setWindowTitle("Excluded date")
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Day (YYYY-MM-DD) or range (YYYY-MM-DD..YYYY-MM-DD):"))
        edit = QLineEdit(dates, dlg)
        edit.setPlaceholderText("2026-03-12  or  2026-05-01..2026-05-07")
        lay.addWidget(edit)
        state = {"decks": decks}
        deck_btn = QPushButton(dlg)

        def refresh_btn():
            n = len(state["decks"])
            deck_btn.setText("Decks: all" if not n else f"Decks: {n} selected")

        def pick():
            d = DeckMultiSelectDialog(state["decks"] or None, parent=dlg)
            if d.exec():
                sel = d.selected_deck_ids
                state["decks"] = [int(x) for x in (sel or []) if x != "deleted"]
                refresh_btn()

        deck_btn.clicked.connect(pick)
        refresh_btn()
        lay.addWidget(deck_btn)
        row = QHBoxLayout()
        row.addStretch(1)
        ok = QPushButton("OK", dlg)
        cancel = QPushButton("Cancel", dlg)
        ok.clicked.connect(dlg.accept)
        cancel.clicked.connect(dlg.reject)
        row.addWidget(cancel)
        row.addWidget(ok)
        lay.addLayout(row)
        while dlg.exec():
            clean = self._valid_dates(edit.text())
            if clean is None:
                showWarning("Invalid date.\nUse YYYY-MM-DD or YYYY-MM-DD..YYYY-MM-DD.", parent=dlg)
                continue
            return {"dates": clean, "decks": state["decks"]} if state["decks"] else clean
        return None

    def _add_date_rule(self):
        entry = self._ask_rule()
        if entry is not None:
            self._add_rule_item(entry)

    def _edit_date_rule(self):
        item = self.dates_list.currentItem()
        if item is None:
            return
        entry = self._ask_rule(item.data(Qt.ItemDataRole.UserRole))
        if entry is not None:
            item.setData(Qt.ItemDataRole.UserRole, entry)
            item.setText(self._rule_text(entry))

    def _remove_date_rule(self):
        row = self.dates_list.currentRow()
        if row >= 0:
            self.dates_list.takeItem(row)

    def save(self):
        new_dates = [
            self.dates_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.dates_list.count())
        ]
        self.addon_config.config[Config.EXCLUDED_DATES] = new_dates
        new_excluded = []
        for row in self.deck_rows:
            if not row['check'].isChecked():
                new_excluded.append(row['did'])

        self.addon_config.config[Config.EXCLUDED_DECKS] = new_excluded
        self.addon_config.config[Config.DECK_COLORS] = self.deck_colors
        self.addon_config.write_config()
        self.accept()

    def refresh_styles(self):
        is_dark = theme_manager.get_night_mode()
        set_qss(self, get_settings_dialog_style(is_dark, self.addon_config.config))

