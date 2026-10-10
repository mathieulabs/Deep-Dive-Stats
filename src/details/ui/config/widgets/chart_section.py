# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from __future__ import annotations

from aqt.qt import QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QVBoxLayout

from ... import Config
from .components import SettingsSlider


def _box_style_keys(dialog):
    if getattr(dialog, "type", None) == "text_label":
        return (
            Config.TEXT_WIDGET_SHOW_GLASS,
            Config.TEXT_WIDGET_GLASS_INTENSITY,
            Config.TEXT_WIDGET_GLASS_BORDER,
        )
    return (
        Config.PINNED_GLASS,
        Config.PINNED_GLASS_INTENSITY,
        Config.PINNED_GLASS_BORDER,
    )


def _hover_border_key(dialog):
    if getattr(dialog, "type", None) == "text_label":
        return Config.TEXT_WIDGET_HOVER_BORDER
    return Config.PINNED_HOVER_BORDER


def setup_chart_settings(dialog, *, include_chart_appearance: bool = True) -> None:
    show_key, intensity_key, border_key = _box_style_keys(dialog)
    group = QGroupBox("Background Box Settings")
    layout = QVBoxLayout(group)

    dialog.glass_cb = QCheckBox("Show Background Box")
    dialog.glass_cb.setChecked(dialog.addon_config.get(show_key, True))
    layout.addWidget(dialog.glass_cb)

    if dialog.type == "activity":
        dialog.avg_cb = QCheckBox("Show Average Line")
        dialog.avg_cb.setChecked(dialog.widget_def.get("show_average", True))
        layout.addWidget(dialog.avg_cb)

        dialog.cum_cb = QCheckBox("Show Cumulative Line")
        dialog.cum_cb.setChecked(dialog.widget_def.get("show_cumulative", True))
        layout.addWidget(dialog.cum_cb)

    dialog.int_slider = SettingsSlider(
        "Background Intensity",
        dialog.addon_config.get(intensity_key, 20),
        0,
        100,
        suffix="%",
    )
    layout.addWidget(dialog.int_slider)

    dialog.border_slider = SettingsSlider(
        "Border Opacity",
        dialog.addon_config.get(border_key, 50),
        0,
        100,
        suffix="%",
    )
    layout.addWidget(dialog.border_slider)

    # Like the stat cards' "Hover Effect": the border brightens on hover unless off.
    dialog.hover_border_cb = QCheckBox("Show Hover Border")
    dialog.hover_border_cb.setToolTip("Brighten the box border when the mouse is over it.")
    dialog.hover_border_cb.setChecked(dialog.addon_config.get(_hover_border_key(dialog), True))
    layout.addWidget(dialog.hover_border_cb)
    dialog.content_layout.addWidget(group)

    if include_chart_appearance:
        # Chart appearance group - opacity applies to bars/slices/lines.
        opacity_defaults = {"card_counts": 100, "distribution": 100, "retention": 100}
        default_opacity = opacity_defaults.get(dialog.type, 100)
        appearance_group = QGroupBox("Chart Appearance")
        appearance_layout = QVBoxLayout(appearance_group)
        dialog.chart_opacity_slider = SettingsSlider(
            "Graph Opacity",
            dialog.widget_def.get("chart_opacity", default_opacity),
            0,
            100,
            suffix="%",
        )
        appearance_layout.addWidget(dialog.chart_opacity_slider)

        if dialog.type == "card_counts":
            dialog.show_legend_cb = QCheckBox("Show Legend")
            dialog.show_legend_cb.setToolTip("The list of card types with their counts, on the right of the donut. Off keeps only the donut.")
            dialog.show_legend_cb.setChecked(bool(dialog.widget_def.get("show_legend", True)))
            appearance_layout.addWidget(dialog.show_legend_cb)

            legend_row = QHBoxLayout()
            legend_row.addWidget(QLabel("Legend Layout"))
            dialog.legend_mode_combo = QComboBox()
            for _label, _mode in (("Auto", "auto"), ("Always next to the donut", "always"), ("On hover", "hover")):
                dialog.legend_mode_combo.addItem(_label, _mode)
            _idx = dialog.legend_mode_combo.findData(dialog.widget_def.get("legend_mode", "auto"))
            dialog.legend_mode_combo.setCurrentIndex(max(0, _idx))
            dialog.legend_mode_combo.setToolTip(
                "Auto: the legend sits next to the donut when there is room to read it, "
                "otherwise the donut takes the whole space and a list icon shows the legend on hover."
            )
            dialog.legend_mode_combo.setEnabled(dialog.show_legend_cb.isChecked())
            dialog.show_legend_cb.toggled.connect(dialog.legend_mode_combo.setEnabled)
            legend_row.addWidget(dialog.legend_mode_combo, 1)
            appearance_layout.addLayout(legend_row)

        def _global_style(key):
            try:
                _top = getattr(dialog, "theme_config", None)
                _default = 80 if key == "Chart_Line_Opacity" else 43 if key == "Chart_Bar_Gradient" else 100
                _fallback = _top.get(key, _default) if isinstance(_top, dict) else _default
                return int(dialog.addon_config.get(key, _fallback))
            except Exception:
                return 80 if key == "Chart_Line_Opacity" else 43 if key == "Chart_Bar_Gradient" else 100

        if dialog.type not in ("card_counts", "distribution"):
            dialog.line_opacity_slider = SettingsSlider(
                "Total / Average Lines",
                dialog.widget_def.get("line_opacity", _global_style("Chart_Line_Opacity")),
                0,
                200,
                suffix="%",
            )
            appearance_layout.addWidget(dialog.line_opacity_slider)
            dialog.bar_gradient_slider = SettingsSlider(
                "Bar Gradient",
                dialog.widget_def.get("bar_gradient", _global_style("Chart_Bar_Gradient")),
                0,
                100,
                suffix="%",
            )
            appearance_layout.addWidget(dialog.bar_gradient_slider)

            def _global_flag(key):
                return bool(dialog.addon_config.get(key, True))

            # Same as the sliders above: follow Settings > General > Chart Style
            # unless changed here for this chart.
            for _attr, _key, _conf_key, _text, _tip in (
                ("show_grid_cb", "show_grid", Config.CHART_SHOW_GRID, "Grid Lines",
                 "Horizontal guide lines behind this chart. Off keeps only the baseline."),
            ):
                _cb = QCheckBox(_text)
                _cb.setToolTip(_tip)
                _cb.setChecked(bool(dialog.widget_def.get(_key, _global_flag(_conf_key))))
                setattr(dialog, _attr, _cb)
                appearance_layout.addWidget(_cb)
        dialog.content_layout.addWidget(appearance_group)

        from ....widgets.chart_utils.tooltip_fields import CHART_TOOLTIP_FIELDS, build_tooltip_group

        if dialog.type in CHART_TOOLTIP_FIELDS:
            dialog.tooltip_checks = build_tooltip_group(
                dialog.content_layout,
                CHART_TOOLTIP_FIELDS[dialog.type],
                dialog.widget_def.get("tooltip_hidden", []),
                title="Tooltip Lines",
            )

        if dialog.type in ("future_due", "stability", "review_intervals"):
            # Which four radio buttons the chart header shows.
            if dialog.type == "future_due":
                from ....widgets.common.future_due_filters import FUTURE_DUE_DAY_CHOICES, normalize_future_due_days
                dialog.range_btn_key = "radio_ranges"
                choices = [(d, long_) for d, long_, _s in FUTURE_DUE_DAY_CHOICES]
                current = normalize_future_due_days(dialog.widget_def.get("radio_ranges"))
            else:
                from ....widgets.common.fsrs_filters import FSRS_FILTER_CHOICES, normalize_fsrs_filter_modes
                dialog.range_btn_key = "filter_modes"
                choices = [(m, long_) for m, long_, _s in FSRS_FILTER_CHOICES]
                current = normalize_fsrs_filter_modes(dialog.widget_def.get("filter_modes"))
            range_group = QGroupBox("Range Buttons")
            range_layout = QFormLayout(range_group)
            dialog.range_btn_combos = []
            from .range_button_row import RangeButtonRow
            _kind = "days" if dialog.type == "future_due" else "fsrs"
            for _i in range(4):
                _combo = RangeButtonRow(_kind, choices, current[_i])
                _combo.setToolTip("Pick four different values, or Custom. They are shown in order, 'all' last.")
                range_layout.addRow(f"Button {_i + 1}:", _combo)
                dialog.range_btn_combos.append(_combo)
            dialog.content_layout.addWidget(range_group)

