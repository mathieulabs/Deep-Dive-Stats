# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations

from aqt.qt import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTabWidget,
    Qt,
    QVBoxLayout,
    QWidget,
)

from ... import Config
from ... import ThemePalettes
from ..theme.ui_helpers import (
    add_data_color_group,
    build_pinned_theme_mode_group,
    build_theme_base_mode_selector,
    apply_theme_card_filter,
    build_theme_cards_container,
    build_theme_filter_bar,
    get_builtin_theme_defs,
    get_theme_color_keys,
)
from .....qss import set_qss


def build_colors_tab(dialog) -> None:
    colors_tab = QWidget(dialog.tabs_widget)
    colors_main_layout = QVBoxLayout(colors_tab)
    colors_main_layout.setContentsMargins(0, 0, 0, 0)

    dialog.colors_scroll = QScrollArea(colors_tab)
    colors_scroll = dialog.colors_scroll
    colors_scroll.setWidgetResizable(True)
    colors_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    colors_scroll_content = QWidget()
    colors_scroll_content.setObjectName("scroll_content")
    colors_layout = QVBoxLayout(colors_scroll_content)
    colors_layout.setContentsMargins(15, 15, 15, 15)
    colors_layout.setSpacing(12)
    colors_scroll.setWidget(colors_scroll_content)
    colors_main_layout.addWidget(colors_scroll)

    group_theme = QGroupBox("Theme")
    layout_theme = QVBoxLayout(group_theme)
    layout_theme.setSpacing(10)

    dialog._builtin_theme_defs = get_builtin_theme_defs()
    current_preset = dialog.parent_dialog.addon_config.config.get(
        Config.THEME_PRESET, ThemePalettes.NATIVE
    )
    dialog._theme_card_widgets = {}
    dialog.theme_cards_container, dialog.theme_cards_grid = build_theme_cards_container(
        "theme_cards_container"
    )
    dialog._rebuild_theme_cards(current_preset)

    info_lbl = QLabel(
        "Anki Native follows Anki's own light/dark mode. Any other theme overrides "
        "the colors of the Details window and menus (pinned widgets are set below). "
        "For other themes, Base Mode sets how graph lines, borders and text adapt "
        "to light or dark, and is saved with the preset."
    )
    info_lbl.setObjectName("theme_info_label")
    info_lbl.setWordWrap(True)

    (
        pinned_mode_group,
        dialog.pinned_theme_mode_combo,
        dialog.pinned_theme_mode_hint,
    ) = build_pinned_theme_mode_group(dialog._on_pinned_theme_mode_changed)
    dialog.theme_tabs = QTabWidget()
    details_theme_tab = QWidget()
    details_theme_layout = QVBoxLayout(details_theme_tab)
    details_theme_layout.setContentsMargins(0, 0, 0, 0)
    details_theme_layout.setSpacing(8)
    filter_row, dialog._theme_filter_state = build_theme_filter_bar(
        lambda: apply_theme_card_filter(
            dialog.theme_cards_grid,
            dialog._theme_card_widgets,
            dialog._theme_filter_state,
            columns=3,
        )
    )
    details_theme_layout.addLayout(filter_row)
    details_theme_layout.addWidget(dialog.theme_cards_container)
    details_theme_layout.addWidget(info_lbl)

    (
        base_mode_row,
        dialog.theme_base_mode_label,
        dialog.theme_base_mode_selector,
        dialog.theme_base_mode_buttons,
    ) = build_theme_base_mode_selector(
        details_theme_tab,
        dialog.on_theme_base_mode_changed,
    )
    details_theme_layout.addLayout(base_mode_row)

    dialog.group_theme_manual = QGroupBox("Theme Colors")
    layout_manual = QGridLayout(dialog.group_theme_manual)
    layout_manual.setSpacing(6)
    layout_manual.setContentsMargins(10, 10, 10, 10)

    dialog._theme_color_buttons = {}
    dialog._theme_hex_labels = {}
    dialog._theme_reset_buttons = {}
    dialog._theme_keys = get_theme_color_keys()
    for i, (key, label_text) in enumerate(dialog._theme_keys):
        row_i, col_pair = divmod(i, 2)
        base_col = col_pair * 2
        lbl = QLabel(label_text)
        btn = dialog._make_theme_color_control(key)
        layout_manual.addWidget(lbl, row_i, base_col)
        layout_manual.addWidget(btn, row_i, base_col + 1)
    details_theme_layout.addWidget(dialog.group_theme_manual)

    actions_row = QHBoxLayout()
    dialog.update_theme_preset_btn = QPushButton("Update Preset")
    dialog.update_theme_preset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    dialog.update_theme_preset_btn.clicked.connect(dialog.on_update_theme_preset)
    actions_row.addWidget(dialog.update_theme_preset_btn)
    dialog.save_theme_preset_btn = QPushButton("Save as New Preset")
    dialog.save_theme_preset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    dialog.save_theme_preset_btn.clicked.connect(dialog.on_save_theme_preset)
    actions_row.addWidget(dialog.save_theme_preset_btn)
    dialog.delete_theme_preset_btn = QPushButton("Delete Preset")
    dialog.delete_theme_preset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    dialog.delete_theme_preset_btn.clicked.connect(dialog.on_delete_theme_preset)
    actions_row.addWidget(dialog.delete_theme_preset_btn)
    actions_row.addStretch()
    details_theme_layout.addLayout(actions_row)
    details_theme_layout.addStretch()

    pinned_theme_tab = QWidget()
    pinned_theme_layout = QVBoxLayout(pinned_theme_tab)
    pinned_theme_layout.setContentsMargins(0, 0, 0, 0)
    pinned_theme_layout.setSpacing(8)

    (
        dialog.pinned_theme_cards_container,
        dialog.pinned_theme_cards_grid,
    ) = build_theme_cards_container("pinned_theme_cards_container")
    dialog._pinned_theme_card_widgets = {}
    pinned_theme_layout.addWidget(dialog.pinned_theme_cards_container)

    (
        pinned_mode_row,
        dialog.pinned_theme_base_mode_label,
        dialog.pinned_theme_base_mode_selector,
        dialog.pinned_theme_base_mode_buttons,
    ) = build_theme_base_mode_selector(
        pinned_theme_tab,
        dialog.on_pinned_theme_base_mode_changed,
    )
    dialog.pinned_theme_base_mode_label.setText("Pinned Graph Adaptation Mode:")
    pinned_theme_layout.addLayout(pinned_mode_row)

    dialog.group_pinned_theme_manual = QGroupBox("Pinned Theme Colors")
    layout_pinned_manual = QGridLayout(dialog.group_pinned_theme_manual)
    layout_pinned_manual.setSpacing(6)
    layout_pinned_manual.setContentsMargins(10, 10, 10, 10)
    dialog._pinned_theme_color_buttons = {}
    dialog._pinned_theme_hex_labels = {}
    dialog._pinned_theme_reset_buttons = {}
    for i, (key, label_text) in enumerate(dialog._theme_keys):
        row_i, col_pair = divmod(i, 2)
        base_col = col_pair * 2
        lbl = QLabel(label_text)
        btn = dialog._make_pinned_theme_color_control(key)
        layout_pinned_manual.addWidget(lbl, row_i, base_col)
        layout_pinned_manual.addWidget(btn, row_i, base_col + 1)
    pinned_theme_layout.addWidget(dialog.group_pinned_theme_manual)
    pinned_theme_layout.addStretch()

    dialog.pinned_theme_tab = pinned_theme_tab
    dialog.theme_tabs.addTab(details_theme_tab, "Details")
    dialog.theme_tabs.currentChanged.connect(lambda _i: dialog._refresh_data_color_controls())
    layout_theme.addWidget(dialog.theme_tabs)
    layout_theme.addWidget(pinned_mode_group)

    dialog._refresh_theme_color_controls()
    dialog._refresh_pinned_theme_controls()
    dialog._update_theme_preset_action_buttons()

    colors_layout.addWidget(group_theme)

    from ..theme.backdrop_ui import build_backdrop_group

    colors_layout.addWidget(build_backdrop_group(dialog))

    dialog.data_color_context_hint = QLabel("")
    dialog.data_color_context_hint.setObjectName("theme_info_label")
    dialog.data_color_context_hint.setWordWrap(True)
    colors_layout.addWidget(dialog.data_color_context_hint)

    dialog._color_buttons = {}
    dialog._reset_buttons = {}
    dialog._hex_labels = {}

    stat_color_rows = [
        (Config.COLOR_TIME, "Total Time"),
        (Config.COLOR_AVG_TIME, "Time/Card"),
        (Config.COLOR_REVIEWS, "Reviews"),
        (Config.COLOR_RETENTION, "Retention"),
        (Config.COLOR_STREAK, "Streak"),
        (Config.COLOR_ACTIVE_DAYS, "Active Days"),
    ]
    add_data_color_group(colors_layout, "Stat Colors", stat_color_rows, dialog._make_color_button)

    break_color_rows = [
        (Config.COLOR_MATURE, "Mature"),
        (Config.COLOR_YOUNG, "Young"),
        (Config.COLOR_LEARN, "Learning"),
        (Config.COLOR_RELEARN, "Relearning"),
        (Config.COLOR_CRAM, "Filtered"),
        (Config.COLOR_NEW, "New"),
        (Config.COLOR_SUSPENDED, "Suspended"),
        (Config.COLOR_BURIED, "Buried"),
    ]
    add_data_color_group(colors_layout, "Card Type Colors", break_color_rows, dialog._make_color_button)

    add_data_color_group(
        colors_layout,
        "Button Colors (Again / Hard / Good / Easy)",
        [
            (Config.COLOR_AGAIN, "Again"),
            (Config.COLOR_HARD, "Hard"),
            (Config.COLOR_GOOD, "Good"),
            (Config.COLOR_EASY, "Easy"),
        ],
        dialog._make_color_button,
    )

    add_data_color_group(
        colors_layout,
        "Chart Colors",
        [
            (Config.COLOR_BAR, "Bar / Line"),
            (Config.COLOR_FUTURE_DUE, "Future Due"),
            (Config.COLOR_BACKLOG, "Backlog"),
            (Config.COLOR_DELETED, "Deleted"),
            (Config.HEATMAP_COLOR, "Heatmap"),
            (Config.COLOR_GRADIENT_LOW, "Gradient Low"),
            (Config.COLOR_GRADIENT_HIGH, "Gradient High"),
        ],
        dialog._make_color_button,
    )

    reset_btn = QPushButton("Reset Colors to Default")
    reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    set_qss(reset_btn, 
        """
        QPushButton {
            background: rgba(244, 67, 54, 0.15);
            color: #F44336;
            border: 1px solid rgba(244, 67, 54, 0.3);
            border-radius: 16px;
            padding: 8px 18px;
            font-weight: 600;
        }
        QPushButton:hover {
            background: rgba(244, 67, 54, 0.25);
            border-color: rgba(244, 67, 54, 0.5);
        }
    """
    )
    reset_btn.clicked.connect(dialog._reset_colors_to_default)
    colors_layout.addWidget(reset_btn)
    colors_layout.addStretch()

    dialog._refresh_data_color_controls()

    dialog.tabs_widget.insertTab(1, colors_tab, "Colors")

