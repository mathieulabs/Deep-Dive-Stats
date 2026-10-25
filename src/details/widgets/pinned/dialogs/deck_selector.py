# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QHBoxLayout, Qt
from aqt import mw
from ...chart_utils.theme import ThemeContext, apply_theme_context, resolve_widget_theme_context
from .....qss import set_qss

class DeckSelectorDialog(QDialog):
    def __init__(self, current_deck_id, parent=None, show_adaptive=True, is_deep_dive=False):
        super().__init__(parent)
        self.setWindowTitle("Select Deck" if is_deep_dive else "Select Widget Deck Binding")
        self.resize(350, 450)
        self.selected_deck_id = current_deck_id

        # Theme: the details/deep-dive context follows the Details theme preset and
        # adaptation mode, the pinned context always follows native Anki light/dark.
        detected_ctx = resolve_widget_theme_context(parent, default=ThemeContext.PINNED)
        use_details_theme = bool(is_deep_dive or detected_ctx == ThemeContext.DETAILS)
        apply_theme_context(self, ThemeContext.DETAILS if use_details_theme else ThemeContext.PINNED)

        if use_details_theme and parent is not None and hasattr(parent, "addon_config"):
            self.addon_config = parent.addon_config
            from ....ui.theme import apply_styles
            apply_styles(self)
        else:
            from ...chart_utils.theme import settings_dialog_qss_for
            set_qss(self, settings_dialog_qss_for(
                ThemeContext.DETAILS if use_details_theme else ThemeContext.PINNED
            ))

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)

        top_btn_layout = QHBoxLayout()
        top_btn_layout.setSpacing(10)

        if show_adaptive:
            self.adaptive_btn = QPushButton("Adaptive")
            self.adaptive_btn.setToolTip("Follows the currently active deck in Anki.")
            self.adaptive_btn.clicked.connect(self._select_adaptive)
            if current_deck_id is None:
                self.adaptive_btn.setDefault(True)
            top_btn_layout.addWidget(self.adaptive_btn)

        self.collection_btn = QPushButton("Collection")
        self.collection_btn.setToolTip("Global statistics for your entire Anki collection.")
        self.collection_btn.clicked.connect(self._select_collection)
        if current_deck_id == 0 or current_deck_id == "0":
            self.collection_btn.setDefault(True)

        top_btn_layout.addWidget(self.collection_btn)
        main_layout.addLayout(top_btn_layout)

        self.search_bar = QLineEdit()
        self.search_bar.setObjectName("search_bar")
        self.search_bar.setPlaceholderText("Search decks...")
        self.search_bar.textChanged.connect(self._filter_decks)
        main_layout.addWidget(self.search_bar)

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(lambda item: self.accept())
        main_layout.addWidget(self.list_widget)

        self.select_btn = QPushButton("Select" if is_deep_dive else "Bind to Selected Deck")
        self.select_btn.clicked.connect(self.accept)
        main_layout.addWidget(self.select_btn)

        self._populate_decks()

        self.search_bar.setFocus()

    def _populate_decks(self):
        decks = sorted(mw.col.decks.all(), key=lambda d: d['name'])
        for d in decks:
            item = QListWidgetItem(d['name'])
            item.setData(Qt.ItemDataRole.UserRole, d['id'])
            self.list_widget.addItem(item)
            if self.selected_deck_id is not None and str(d['id']) == str(self.selected_deck_id):
                item.setSelected(True)
                self.list_widget.scrollToItem(item)

    def _filter_decks(self, text):
        search_text = text.lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(search_text not in item.text().lower())

    def _select_adaptive(self):
        self.selected_deck_id = None
        super().accept()

    def _select_collection(self):
        self.selected_deck_id = 0
        super().accept()

    def accept(self):
        if self.list_widget.selectedItems():
            selected = self.list_widget.selectedItems()[0]
            self.selected_deck_id = selected.data(Qt.ItemDataRole.UserRole)
            super().accept()
