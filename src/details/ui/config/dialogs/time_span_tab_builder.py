# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations

from aqt.qt import (
    QCheckBox,
    QComboBox,
    QDate,
    QDateEdit,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..shared import RANGE_OPTIONS
from .....i18n import tr, tr_name


def build_time_span_tab(dialog) -> None:
    tabs_tab = QWidget(dialog.tabs_widget)
    tabs_layout = QVBoxLayout(tabs_tab)
    tabs_layout.setContentsMargins(10, 10, 10, 10)

    list_label = QLabel(tr("Tabs:"))
    tabs_layout.addWidget(list_label)

    dialog.tabs_list = QListWidget()
    dialog.tabs_list.currentRowChanged.connect(dialog.on_tab_selected)
    tabs_layout.addWidget(dialog.tabs_list)

    btn_layout = QHBoxLayout()
    dialog.add_btn = QPushButton(tr("+ Add Tab"))
    dialog.add_btn.clicked.connect(dialog.add_tab)
    dialog.remove_btn = QPushButton(tr("- Remove Tab"))
    dialog.remove_btn.clicked.connect(dialog.remove_tab)
    dialog.reset_defaults_btn = QPushButton(tr("Reset Defaults"))
    dialog.reset_defaults_btn.clicked.connect(dialog.reset_defaults)
    btn_layout.addWidget(dialog.add_btn)
    btn_layout.addWidget(dialog.remove_btn)
    btn_layout.addWidget(dialog.reset_defaults_btn)
    btn_layout.addStretch()
    tabs_layout.addLayout(btn_layout)

    scroll_area = QScrollArea(tabs_tab)
    scroll_area.setWidgetResizable(True)
    scroll_content = QWidget(scroll_area)
    scroll_content.setObjectName("scroll_content")
    scroll_layout = QVBoxLayout(scroll_content)
    scroll_layout.setContentsMargins(10, 10, 10, 10)
    scroll_area.setWidget(scroll_content)
    tabs_layout.addWidget(scroll_area)

    dialog.group_general = QGroupBox(tr("General"))
    layout_gen = QFormLayout(dialog.group_general)
    dialog.enabled_check = QCheckBox(parent=dialog.group_general)
    dialog.enabled_check.stateChanged.connect(dialog.on_enabled_changed)
    layout_gen.addRow(tr("Active:"), dialog.enabled_check)

    dialog.title_edit = QLineEdit(parent=dialog.group_general)
    dialog.title_edit.textChanged.connect(dialog.on_title_changed)
    layout_gen.addRow(tr("Title:"), dialog.title_edit)

    dialog.full_name_check = QCheckBox(parent=dialog.group_general)
    dialog.full_name_check.stateChanged.connect(dialog.on_full_name_changed)
    layout_gen.addRow(tr("Show Full Deck Path:"), dialog.full_name_check)
    scroll_layout.addWidget(dialog.group_general)

    dialog.group_range = QGroupBox(tr("Time Range"))
    layout_range = QFormLayout(dialog.group_range)
    dialog.range_combo = QComboBox()
    for label, value in RANGE_OPTIONS:
        label = tr_name(label)
        dialog.range_combo.addItem(label, value)
    dialog.range_combo.currentIndexChanged.connect(dialog.on_range_changed)
    layout_range.addRow(tr("Range:"), dialog.range_combo)

    dialog.custom_type_label = QLabel(tr("Type:"))
    dialog.custom_type_combo = QComboBox()
    dialog.custom_type_combo.addItem(tr("Relative Days"), "relative")
    dialog.custom_type_combo.addItem(tr("Date Range"), "absolute")
    dialog.custom_type_combo.currentIndexChanged.connect(dialog.on_custom_type_changed)
    layout_range.addRow(dialog.custom_type_label, dialog.custom_type_combo)

    dialog.days_label = QLabel(tr("Past Days:"))
    dialog.days_spin = QSpinBox()
    dialog.days_spin.setRange(1, 9999)
    dialog.days_spin.valueChanged.connect(dialog.on_days_changed)
    layout_range.addRow(dialog.days_label, dialog.days_spin)

    dialog.start_date_label = QLabel(tr("Start Date:"))
    dialog.start_date_edit = QDateEdit()
    dialog.start_date_edit.setCalendarPopup(True)
    dialog.start_date_edit.setDate(QDate.currentDate())
    dialog.start_date_edit.dateChanged.connect(dialog.on_start_date_changed)
    layout_range.addRow(dialog.start_date_label, dialog.start_date_edit)

    dialog.end_date_label = QLabel(tr("End Date:"))
    dialog.end_date_edit = QDateEdit()
    dialog.end_date_edit.setCalendarPopup(True)
    dialog.end_date_edit.setDate(QDate.currentDate())
    dialog.end_date_edit.dateChanged.connect(dialog.on_end_date_changed)
    layout_range.addRow(dialog.end_date_label, dialog.end_date_edit)

    dialog.to_today_label = QLabel(tr("Until today:"))
    dialog.to_today_check = QCheckBox()
    dialog.to_today_check.setToolTip(tr("The range ends today and grows by one day each day."))
    dialog.to_today_check.stateChanged.connect(dialog.on_to_today_changed)
    layout_range.addRow(dialog.to_today_label, dialog.to_today_check)
    scroll_layout.addWidget(dialog.group_range)

    dialog.group_format = QGroupBox(tr("Formatting"))
    layout_fmt = QFormLayout(dialog.group_format)
    dialog.decimal_check = QCheckBox(parent=scroll_content)
    dialog.decimal_check.stateChanged.connect(
        lambda state: dialog._save_tab_checkbox("use_decimal", state)
    )
    layout_fmt.addRow(tr("Use Decimal:"), dialog.decimal_check)
    scroll_layout.addWidget(dialog.group_format)

    dialog.group_cols = QGroupBox(tr("Columns to Show"))
    layout_cols = QVBoxLayout(dialog.group_cols)
    column_checkboxes = [
        ("show_time_check", tr("Time"), "show_time"),
        ("show_reviews_check", tr("Reviews"), "show_reviews"),
        ("retention_check", tr("Retention (Total)"), "show_retention"),
        ("retention_young_check", tr("Retention (Young)"), "show_retention_young"),
        ("retention_mature_check", tr("Retention (Mature)"), "show_retention_mature"),
        ("avg_time_check", tr("Avg Time"), "show_avg_time"),
        ("show_counts_check", tr("Counts"), "show_counts"),
        ("show_streak_check", tr("Streak"), "show_streak"),
        ("show_active_days_check", tr("Active Days"), "show_active_days"),
        ("show_longest_streak_check", tr("Longest Streak"), "show_longest_streak"),
        ("show_buttons_dist_check", tr("Combined Buttons"), "show_buttons_dist"),
        ("show_forecast_check", tr("Smart Forecast"), "show_forecast"),
    ]
    for attr_name, label, config_key in column_checkboxes:
        checkbox = QCheckBox(label, parent=dialog.group_cols)
        checkbox.stateChanged.connect(
            lambda state, key=config_key: dialog._save_tab_checkbox(key, state)
        )
        setattr(dialog, attr_name, checkbox)
        layout_cols.addWidget(checkbox)

    scroll_layout.addWidget(dialog.group_cols)
    scroll_layout.addStretch()
    dialog.tabs_widget.addTab(tabs_tab, tr("Time Span"))

