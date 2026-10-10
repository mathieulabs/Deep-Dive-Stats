# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Context menu entries to hide review types from the Activity chart."""
from aqt.qt import QAction

from ...logic.data.transforms.activity_series import REVIEW_TYPE_CHOICES, normalize_hidden_types


def add_review_type_actions(menu, hidden, on_change):
    """Add a "Review Types" submenu. `on_change(hidden_keys)` gets the new list (empty = all shown).

    At least one type always stays on, so the chart never ends up blank by accident.
    """
    hidden = set(normalize_hidden_types(hidden))
    sub = menu.addMenu("Review Types")
    visible_count = len(REVIEW_TYPE_CHOICES) - len(hidden)
    for key, label in REVIEW_TYPE_CHOICES:
        act = QAction(label, sub)
        act.setCheckable(True)
        shown = key not in hidden
        act.setChecked(shown)
        if shown and visible_count <= 1:
            act.setEnabled(False)

        def _toggled(checked, k=key):
            new_hidden = set(hidden)
            if checked:
                new_hidden.discard(k)
            else:
                new_hidden.add(k)
            on_change([ck for ck, _ in REVIEW_TYPE_CHOICES if ck in new_hidden])

        act.triggered.connect(_toggled)
        sub.addAction(act)
    return sub
