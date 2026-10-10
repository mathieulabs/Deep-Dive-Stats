# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations

from aqt.qt import QCheckBox, QComboBox, QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ... import Config
from ...theme.icons import get_svg_icon
from .components import SettingsSlider
from .....qss import set_qss


def setup_heatmap_settings(dialog) -> None:
    group_layout = QGroupBox("Layout && appearance")
    layout_playout = QVBoxLayout(group_layout)

    if dialog.is_grid:
        row = QHBoxLayout()
        dialog.hide_labels_cb = QCheckBox("Hide Labels")
        dialog.hide_labels_cb.setChecked(dialog.addon_config.get(Config.HEATMAP_HIDE_LABELS, False))
        row.addWidget(dialog.hide_labels_cb)
        dialog.show_legend_cb = QCheckBox("Show Legend")
        dialog.show_legend_cb.setToolTip("Color legend under the heatmap, with the value each color starts at.")
        dialog.show_legend_cb.setChecked(dialog.addon_config.get(Config.HEATMAP_SHOW_LEGEND, True))
        row.addWidget(dialog.show_legend_cb)
        row.addStretch()
        layout_playout.addLayout(row)
    else:
        dialog.scale_slider = SettingsSlider(
            "Overall Scale",
            dialog.addon_config.get(Config.HEATMAP_SCALE, 100),
            50,
            200,
            suffix="%",
        )
        layout_playout.addWidget(dialog.scale_slider)

        nav_lay = QHBoxLayout()
        nav_lay.addWidget(QLabel("Navigation Position:"))
        dialog.nav_combo = QComboBox()
        dialog.nav_combo.addItem("Top Right", "top_right")
        dialog.nav_combo.addItem("Top Left", "top_left")
        dialog.nav_combo.addItem("Bottom Right", "bottom_right")
        dialog.nav_combo.addItem("Bottom Left", "bottom_left")
        current_nav = dialog.addon_config.get(Config.HEATMAP_NAV_POS, "top_right")
        idx = dialog.nav_combo.findData(current_nav)
        if idx >= 0:
            dialog.nav_combo.setCurrentIndex(idx)
        nav_lay.addWidget(dialog.nav_combo)
        layout_playout.addLayout(nav_lay)

        toggles_layout = QVBoxLayout()

        dialog.rounding_slider = SettingsSlider(
            "Corner Radius",
            dialog.addon_config.get(Config.HEATMAP_ROUNDING, 30),
            0,
            100,
            suffix="%",
        )
        toggles_layout.addWidget(dialog.rounding_slider)

        row2 = QHBoxLayout()
        dialog.hide_title_cb = QCheckBox("Hide Title")
        dialog.hide_title_cb.setChecked(dialog.addon_config.get(Config.HEATMAP_HIDE_TITLE, True))
        row2.addWidget(dialog.hide_title_cb)

        dialog.hide_labels_cb = QCheckBox("Hide Labels")
        dialog.hide_labels_cb.setChecked(dialog.addon_config.get(Config.HEATMAP_HIDE_LABELS, False))
        row2.addWidget(dialog.hide_labels_cb)
        dialog.show_legend_cb = QCheckBox("Show Legend")
        dialog.show_legend_cb.setToolTip("Color legend under the heatmap, with the value each color starts at.")
        dialog.show_legend_cb.setChecked(dialog.addon_config.get(Config.HEATMAP_SHOW_LEGEND, True))
        row2.addWidget(dialog.show_legend_cb)
        toggles_layout.addLayout(row2)

        layout_playout.addLayout(toggles_layout)

    dialog.monday_first_cb = QCheckBox("Start Week on Monday")
    dialog.monday_first_cb.setChecked(dialog.addon_config.get(Config.HEATMAP_MONDAY_FIRST, False))
    layout_playout.addWidget(dialog.monday_first_cb)

    dialog.future_cb = QCheckBox("Show Future Reviews")
    dialog.future_cb.setChecked(dialog.addon_config.get(Config.HEATMAP_SHOW_FUTURE, True))
    layout_playout.addWidget(dialog.future_cb)

    dialog.tinted_future_cb = QCheckBox("Tint Future Reviews")
    dialog.tinted_future_cb.setChecked(dialog.addon_config.get(Config.HEATMAP_TINTED_FUTURE, False))
    layout_playout.addWidget(dialog.tinted_future_cb)

    dialog.click_browser_cb = QCheckBox("Click to open Browser")
    dialog.click_browser_cb.setToolTip("Open the Anki Browser for cards reviewed on the clicked day.")
    dialog.click_browser_cb.setChecked(dialog.addon_config.get(Config.HEATMAP_CLICK_BROWSER, True))
    layout_playout.addWidget(dialog.click_browser_cb)
    dialog.content_layout.addWidget(group_layout)

    from ....widgets.chart_utils.tooltip_fields import HEATMAP_TOOLTIP_FIELDS, build_tooltip_group
    dialog.hm_tooltip_checks = build_tooltip_group(
        dialog.content_layout, HEATMAP_TOOLTIP_FIELDS, dialog.addon_config.get(Config.HEATMAP_TOOLTIP_HIDDEN, [])
    )

    group_colors = QGroupBox("Colors && Opacity")
    layout_colors = QVBoxLayout(group_colors)

    if hasattr(dialog, "_get_effective_heatmap_color"):
        dialog.current_color = dialog._get_effective_heatmap_color()
    else:
        dialog.current_color = dialog.addon_config.get(Config.HEATMAP_COLOR, "#3b82f6")
    color_lay = QHBoxLayout()
    color_lay.addWidget(QLabel("Activity Color:"))
    dialog.color_btn = QPushButton(parent=group_colors)
    dialog.color_btn.setFixedWidth(60)
    dialog.color_btn.clicked.connect(dialog._select_color)
    dialog._update_color_button()
    color_lay.addWidget(dialog.color_btn)

    dialog.reset_color_btn = QPushButton(parent=group_colors)
    dialog.reset_color_btn.setIcon(get_svg_icon("rotate-ccw", size=14, context_ref=dialog))
    dialog.reset_color_btn.setFixedSize(24, 24)
    dialog.reset_color_btn.setToolTip("Reset to Default")
    set_qss(dialog.reset_color_btn, 
        "QPushButton { background: transparent; border: none; } "
        "QPushButton:hover { background: rgba(128,128,128,0.18); border-radius: 4px; }"
    )
    dialog.reset_color_btn.clicked.connect(dialog._reset_color)
    color_lay.addWidget(dialog.reset_color_btn)
    color_lay.addStretch()
    layout_colors.addLayout(color_lay)

    dialog.opacity_slider = SettingsSlider(
        "Empty Opacity",
        dialog.addon_config.get(Config.HEATMAP_EMPTY_OPACITY, 15),
        0,
        100,
        suffix="%",
    )
    layout_colors.addWidget(dialog.opacity_slider)

    dialog.filled_opacity_slider = SettingsSlider(
        "Filled Opacity",
        dialog.addon_config.get(Config.HEATMAP_FILLED_OPACITY, 100),
        0,
        100,
        suffix="%",
    )
    layout_colors.addWidget(dialog.filled_opacity_slider)

    dialog.vibrance_slider = SettingsSlider(
        "Saturation",
        dialog.addon_config.get(Config.HEATMAP_VIBRANCE, 100),
        50,
        200,
        suffix="%",
    )
    layout_colors.addWidget(dialog.vibrance_slider)

    dialog.intensity_curve_slider = SettingsSlider(
        "Intensity Curve",
        dialog.addon_config.get(Config.HEATMAP_INTENSITY_CURVE, 100),
        50,
        200,
        suffix="%",
    )
    layout_colors.addWidget(dialog.intensity_curve_slider)

    dialog.hm_levels_slider = SettingsSlider(
        "Color Levels",
        dialog.addon_config.get(Config.HEATMAP_COLOR_LEVELS, 20),
        2,
        30,
    )
    layout_colors.addWidget(dialog.hm_levels_slider)
    dialog.content_layout.addWidget(group_colors)

    group_glass = QGroupBox("Background Box Style")
    layout_glass = QVBoxLayout(group_glass)

    dialog.hm_glass_cb = QCheckBox("Show Background Box")
    dialog.hm_glass_cb.setChecked(dialog.addon_config.get(Config.HEATMAP_SHOW_GLASS, False))

    def update_hm_glass(state):
        enabled = bool(state)
        dialog.hm_int_slider.setEnabled(enabled)
        dialog.hm_border_slider.setEnabled(enabled)

    dialog.hm_glass_cb.stateChanged.connect(update_hm_glass)
    layout_glass.addWidget(dialog.hm_glass_cb)

    dialog.hm_int_slider = SettingsSlider(
        "Intensity",
        dialog.addon_config.get(Config.HEATMAP_GLASS_INTENSITY, 43),
        0,
        100,
        suffix="%",
    )
    layout_glass.addWidget(dialog.hm_int_slider)

    dialog.hm_border_slider = SettingsSlider(
        "Border Opacity",
        dialog.addon_config.get(Config.HEATMAP_GLASS_BORDER, 0),
        0,
        100,
        suffix="%",
    )
    layout_glass.addWidget(dialog.hm_border_slider)

    update_hm_glass(dialog.hm_glass_cb.isChecked())
    dialog.content_layout.addWidget(group_glass)

    if not dialog.is_grid:
        group_modes = QGroupBox("Mode Visibility")
        layout_modes = QVBoxLayout(group_modes)

        dialog.show_cont_cb = QCheckBox("Show continuous mode (infinite)")
        dialog.show_cont_cb.setChecked(dialog.addon_config.get(Config.HEATMAP_SHOW_CONTINUOUS_MODE, True))
        layout_modes.addWidget(dialog.show_cont_cb)

        dialog.show_365_cb = QCheckBox("Show 365-day mode (365)")
        dialog.show_365_cb.setChecked(dialog.addon_config.get(Config.HEATMAP_SHOW_365_MODE, True))
        layout_modes.addWidget(dialog.show_365_cb)

        dialog.show_year_cb = QCheckBox("Show year mode (Y)")
        dialog.show_year_cb.setChecked(dialog.addon_config.get(Config.HEATMAP_SHOW_YEAR_MODE, True))
        layout_modes.addWidget(dialog.show_year_cb)

        dialog.content_layout.addWidget(group_modes)


