# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from aqt.qt import QMessageBox, Qt

from ... import Period
from ....logic.tabs import DEFAULT_DETAILS_TABS
from .tab_mutations import (
    append_new_tab,
    remove_tab as remove_tab_mutation,
    set_tab_enabled,
    set_tab_field,
    set_tab_title,
)

if TYPE_CHECKING:
    from ..dialogs.tabs_config_dialog import DetailedStatsConfigDialog


def save_tab_data(dialog: "DetailedStatsConfigDialog", key: str, value) -> None:
    row = dialog.tabs_list.currentRow()
    set_tab_field(dialog.tabs_data, row, key, value)


def save_tab_checkbox(dialog: "DetailedStatsConfigDialog", key: str, state: int) -> None:
    save_tab_data(dialog, key, state == Qt.CheckState.Checked.value)


def on_custom_type_changed(dialog: "DetailedStatsConfigDialog") -> None:
    update_visibility(dialog)
    save_tab_data(dialog, "custom_type", dialog.custom_type_combo.currentData())


def on_start_date_changed(dialog: "DetailedStatsConfigDialog", date) -> None:
    save_tab_data(dialog, "start_date", date.toString(Qt.DateFormat.ISODate))


def on_end_date_changed(dialog: "DetailedStatsConfigDialog", date) -> None:
    if dialog.to_today_check.isChecked():
        return
    save_tab_data(dialog, "end_date", date.toString(Qt.DateFormat.ISODate))


def on_to_today_changed(dialog: "DetailedStatsConfigDialog", state) -> None:
    checked = state == Qt.CheckState.Checked.value
    dialog.end_date_edit.setEnabled(not checked)
    save_tab_data(dialog, "to_today", checked)
    # An empty end date means "until today" for every range computation.
    save_tab_data(
        dialog, "end_date", "" if checked else dialog.end_date_edit.date().toString(Qt.DateFormat.ISODate)
    )


def update_visibility(dialog: "DetailedStatsConfigDialog") -> None:
    val = dialog.range_combo.currentData()
    is_custom = val == Period.CUSTOM
    dialog.custom_type_label.setVisible(is_custom)
    dialog.custom_type_combo.setVisible(is_custom)

    custom_type = dialog.custom_type_combo.currentData()
    is_relative = is_custom and custom_type == "relative"
    is_absolute = is_custom and custom_type == "absolute"

    dialog.days_spin.setVisible(is_relative)
    dialog.days_label.setVisible(is_relative)

    dialog.start_date_label.setVisible(is_absolute)
    dialog.start_date_edit.setVisible(is_absolute)
    dialog.end_date_label.setVisible(is_absolute)
    dialog.end_date_edit.setVisible(is_absolute)
    dialog.to_today_label.setVisible(is_absolute)
    dialog.to_today_check.setVisible(is_absolute)


def on_enabled_changed(dialog: "DetailedStatsConfigDialog", state) -> None:
    row = dialog.tabs_list.currentRow()
    label = set_tab_enabled(dialog.tabs_data, row, bool(state))
    if label is not None:
        dialog.tabs_list.item(row).setText(label)


def on_title_changed(dialog: "DetailedStatsConfigDialog", text: str) -> None:
    row = dialog.tabs_list.currentRow()
    label = set_tab_title(dialog.tabs_data, row, text)
    if label is not None:
        dialog.tabs_list.item(row).setText(label)


def on_range_changed(dialog: "DetailedStatsConfigDialog") -> None:
    save_tab_data(dialog, "range", dialog.range_combo.currentData())
    update_visibility(dialog)


def on_days_changed(dialog: "DetailedStatsConfigDialog", value: int) -> None:
    save_tab_data(dialog, "days", value)


def add_tab(dialog: "DetailedStatsConfigDialog") -> None:
    new_row = append_new_tab(dialog.tabs_data)
    dialog.load_tabs_list()
    dialog.tabs_list.setCurrentRow(new_row)


def remove_tab(dialog: "DetailedStatsConfigDialog") -> None:
    row = dialog.tabs_list.currentRow()
    if row < 0:
        return
    if len(dialog.tabs_data) <= 1:
        QMessageBox.warning(dialog, "Warning", "You must have at least one tab.")
        return
    removed_title = str(dialog.tabs_data[row].get("title", ""))
    if (
        QMessageBox.question(
            dialog,
            "Remove Tab",
            f"Are you sure you want to remove the tab '{removed_title}'?",
        )
        != QMessageBox.StandardButton.Yes
    ):
        return
    ok, _, _ = remove_tab_mutation(dialog.tabs_data, row, min_count=1)
    if not ok:
        return
    dialog.load_tabs_list()
    new_row = min(row, len(dialog.tabs_data) - 1)
    dialog.tabs_list.setCurrentRow(new_row)


def reset_defaults(dialog: "DetailedStatsConfigDialog") -> None:
    msg = (
        "Are you sure you want to reset all tabs to their default configuration? "
        "This will restore the Today and Yesterday tabs."
    )
    if QMessageBox.question(dialog, "Reset Defaults", msg) != QMessageBox.StandardButton.Yes:
        return

    dialog.tabs_data = copy.deepcopy(DEFAULT_DETAILS_TABS)
    dialog.load_tabs_list()
    if dialog.tabs_list.count() > 0:
        dialog.tabs_list.setCurrentRow(0)

