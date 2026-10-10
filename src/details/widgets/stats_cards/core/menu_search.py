# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""A small search box for long stat-card menus.

Typing in it hides the group submenus and shows the matching entries as one flat list.
"""
from aqt.qt import QAction, QLineEdit, QTimer, QWidget, QWidgetAction, QHBoxLayout


class MenuSearch:
    def __init__(self, menu, placeholder="Search stats..."):
        self.menu = menu
        self.groups = []  # submenu actions, hidden while searching
        self.results = []  # (label, action) flat copies, shown while searching
        self.empty = QAction("No match", menu)
        self.empty.setEnabled(False)
        self.empty.setVisible(False)

        holder = QWidget(menu)
        lay = QHBoxLayout(holder)
        lay.setContentsMargins(8, 4, 8, 4)
        self.edit = QLineEdit(holder)
        self.edit.setPlaceholderText(placeholder)
        self.edit.setClearButtonEnabled(True)
        lay.addWidget(self.edit)
        action = QWidgetAction(menu)
        action.setDefaultWidget(holder)
        menu.addAction(action)
        self.edit.textChanged.connect(self._filter)
        # Popups only give the keyboard to a child once the menu is on screen.
        QTimer.singleShot(0, self.edit.setFocus)

    def add_group(self, submenu):
        self.groups.append(submenu.menuAction())

    def add_result(self, label, action):
        """Add the flat copy of an entry; it stays hidden until the search matches it."""
        action.setVisible(False)
        self.menu.addAction(action)
        self.results.append((label, action))

    def finish(self):
        self.menu.addAction(self.empty)

    def _filter(self, text):
        query = str(text or "").strip().lower()
        for act in self.groups:
            act.setVisible(not query)
        shown = 0
        for label, act in self.results:
            match = bool(query) and query in label.lower()
            act.setVisible(match)
            shown += 1 if match else 0
        self.empty.setVisible(bool(query) and shown == 0)
