# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations

from aqt.qt import QCheckBox, QColor, QColorDialog, QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ... import Config
from .components import SettingsSlider


def setup_facecard_settings(dialog) -> None:
    group = QGroupBox("Card Layout && Size")
    layout = QVBoxLayout(group)

    dialog.scale_spin = SettingsSlider(
        "Visual Scale",
        dialog.addon_config.get(dialog._get_key(Config.FACECARDS_SCALE, Config.DASHBOARD_SCALE), 100),
        50,
        150,
        suffix="%",
    )
    layout.addWidget(dialog.scale_spin)

    dialog.title_size_slider = SettingsSlider(
        "Title Size",
        dialog.addon_config.get(
            dialog._get_key(Config.FACECARDS_TITLE_SIZE, Config.DASHBOARD_TITLE_SIZE), 100
        ),
        70,
        160,
        suffix="%",
    )
    layout.addWidget(dialog.title_size_slider)

    dialog.title_color = str(
        dialog.addon_config.get(
            dialog._get_key(Config.FACECARDS_TITLE_COLOR, Config.DASHBOARD_TITLE_COLOR), ""
        )
        or ""
    )
    color_row = QHBoxLayout()
    color_row.addWidget(QLabel("Title Color"))
    color_row.addStretch()
    dialog.title_color_btn = QPushButton()
    dialog.title_color_btn.setFixedWidth(70)
    dialog.title_color_auto_btn = QPushButton("Auto")
    dialog.title_color_auto_btn.setToolTip("Back to the theme color")
    color_row.addWidget(dialog.title_color_btn)
    color_row.addWidget(dialog.title_color_auto_btn)

    def _paint_title_btn():
        c = dialog.title_color
        if c and QColor(c).isValid():
            dialog.title_color_btn.setText("")
            dialog.title_color_btn.setStyleSheet(f"background-color: {c};")
        else:
            dialog.title_color_btn.setText("Auto")
            dialog.title_color_btn.setStyleSheet("")

    def _pick_title_color():
        start = QColor(dialog.title_color) if dialog.title_color else QColor("#a1a1aa")
        col = QColorDialog.getColor(start, dialog, "Title Color")
        if col.isValid():
            dialog.title_color = col.name()
            _paint_title_btn()
            dialog.apply_live_changes()

    def _auto_title_color():
        dialog.title_color = ""
        _paint_title_btn()
        dialog.apply_live_changes()

    dialog._paint_title_btn = _paint_title_btn
    dialog.title_color_btn.clicked.connect(_pick_title_color)
    dialog.title_color_auto_btn.clicked.connect(_auto_title_color)
    _paint_title_btn()
    layout.addLayout(color_row)

    dialog.hover_effect_cb = QCheckBox("Show Hover Border")
    dialog.hover_effect_cb.setChecked(
        dialog.addon_config.get(
            dialog._get_key(Config.FACECARDS_HOVER_EFFECT, Config.DASHBOARD_HOVER_EFFECT), True
        )
    )
    layout.addWidget(dialog.hover_effect_cb)

    dialog.inline_stats_cb = QCheckBox("Title + Value on same line")
    dialog.inline_stats_cb.setChecked(
        dialog.addon_config.get(
            dialog._get_key(Config.FACECARDS_INLINE_STATS, Config.DASHBOARD_INLINE_STATS), False
        )
    )
    layout.addWidget(dialog.inline_stats_cb)

    dialog.content_layout.addWidget(group)

    glass_group = QGroupBox("Background Box Style")
    glass_layout = QVBoxLayout(glass_group)

    dialog.glass_cb = QCheckBox("Show Background Box")
    initial_glass = dialog.addon_config.get(
        dialog._get_key(Config.FACECARDS_SHOW_GLASS, Config.DASHBOARD_SHOW_GLASS), True
    )
    dialog.glass_cb.setChecked(initial_glass)

    def update_glass_state(state):
        enabled = bool(state)
        dialog.face_int_slider.setEnabled(enabled)
        dialog.face_border_slider.setEnabled(enabled)

    dialog.glass_cb.stateChanged.connect(update_glass_state)
    glass_layout.addWidget(dialog.glass_cb)

    dialog.face_int_slider = SettingsSlider(
        "Intensity",
        dialog.addon_config.get(
            dialog._get_key(Config.FACECARDS_GLASS_INTENSITY, Config.DASHBOARD_GLASS_INTENSITY), 5
        ),
        0,
        100,
        suffix="%",
    )
    glass_layout.addWidget(dialog.face_int_slider)

    dialog.face_border_slider = SettingsSlider(
        "Border Opacity",
        dialog.addon_config.get(
            dialog._get_key(Config.FACECARDS_GLASS_BORDER, Config.DASHBOARD_GLASS_BORDER), 50
        ),
        0,
        100,
        suffix="%",
    )
    glass_layout.addWidget(dialog.face_border_slider)

    update_glass_state(dialog.glass_cb.isChecked())
    dialog.content_layout.addWidget(glass_group)

    shadow_group = QGroupBox("Text Shadows")
    shadow_layout = QVBoxLayout(shadow_group)

    dialog.tshad_slider = SettingsSlider(
        "Title Shadow",
        dialog.addon_config.get(
            dialog._get_key(
                Config.FACECARDS_TITLE_SHADOW_INTENSITY, Config.DASHBOARD_TITLE_SHADOW_INTENSITY
            ),
            40,
        ),
        0,
        100,
        suffix="%",
    )
    shadow_layout.addWidget(dialog.tshad_slider)

    dialog.sshad_slider = SettingsSlider(
        "Value Shadow",
        dialog.addon_config.get(
            dialog._get_key(
                Config.FACECARDS_STAT_SHADOW_INTENSITY, Config.DASHBOARD_STAT_SHADOW_INTENSITY
            ),
            60,
        ),
        0,
        100,
        suffix="%",
    )
    shadow_layout.addWidget(dialog.sshad_slider)

    dialog.content_layout.addWidget(shadow_group)

