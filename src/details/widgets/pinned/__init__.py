# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

"""Pinned widgets package.

- WidgetRegistry: logic.widget_registry
- PinnedViewSelectorDialog: pinned.dialogs.view_selector
"""

from .dialogs import DeckMultiSelectDialog, DELETED_TOKEN, MAIN_MENU_TOKEN, PinnedViewSelectorDialog
from .store import WidgetRegistry

__all__ = [
    "WidgetRegistry",
    "DeckMultiSelectDialog",
    "DELETED_TOKEN",
    "PinnedViewSelectorDialog",
    "MAIN_MENU_TOKEN",
]
