# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Zebra striping for the Deep Dive window tables (setting: Table_Zebra)."""
from aqt.qt import QTableWidget

from .. import Config
from ....config import read_config_value


def zebra_enabled():
    return bool(read_config_value(Config.TABLE_ZEBRA, True))


def apply_zebra(table, enabled=None):
    """Turn the stripes on or off for one table (reads the setting when enabled is None)."""
    table.setAlternatingRowColors(zebra_enabled() if enabled is None else bool(enabled))


def apply_zebra_to_dialog_tables(dialog, enabled):
    for table in dialog.findChildren(QTableWidget):
        apply_zebra(table, enabled)
