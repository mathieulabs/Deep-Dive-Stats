# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Menu of the table columns that can be drawn as a visual (bar) instead of text."""
from aqt.qt import QAction

from .. import Config

# (label, config key, default)
VISUAL_OPTIONS = (
    ("Answer buttons", Config.SHOW_BUTTONS_DIST_VISUAL, True),
    ("Retention", Config.RETENTION_VISUAL_ALL, False),
    ("Retention (young)", Config.RETENTION_VISUAL_YOUNG, False),
    ("Retention (mature)", Config.RETENTION_VISUAL_MATURE, False),
)


def populate_visual_menu(dialog, menu):
    """Add one checkable action per visual to `menu`. Keeps them in dialog._visual_actions."""
    conf = dialog.addon_config.config
    actions = {}
    for label, key, default in VISUAL_OPTIONS:
        act = QAction(label, menu)
        act.setCheckable(True)
        act.setChecked(bool(conf.get(key, default)))
        act.toggled.connect(lambda checked, k=key: dialog.on_visual_option_toggled(k, checked))
        menu.addAction(act)
        actions[key] = act
    return actions
