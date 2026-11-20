# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from __future__ import annotations

from aqt.qt import QCheckBox, QComboBox, QGroupBox, QHBoxLayout, QLabel, QVBoxLayout

from ... import Config
from .components import SettingsSlider
from .....i18n import tr


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


_TOTAL_TYPES = ("activity", "added", "hourly", "future_due", "review_intervals", "stability", "due_today")


def has_total_curve(wtype):
    """A chart drawing a running total (the pale area of Total / Average Lines), so a Total Line of its own."""
    if wtype in _TOTAL_TYPES:
        return True
    try:
        from ....widgets.charts.daily_metrics import BY_TYPE

        m = BY_TYPE.get(wtype)
        return bool(m is not None and m.cumulative and m.unit not in ("level", "seconds"))
    except Exception:
        return False


def total_line_global(dialog):
    """Settings > General > Chart Style's Total Line (0 by default): what a chart without its own follows. A Deep
    Dive chart's dialog edits a small style dict, the whole config is its theme_config."""
    for conf in (getattr(dialog, "addon_config", None), getattr(dialog, "theme_config", None)):
        try:
            v = conf.get(Config.CHART_TOTAL_LINE) if conf is not None else None
        except Exception:
            v = None
        if v is not None:
            try:
                return int(v)
            except (TypeError, ValueError):
                pass
    return 0


def setup_chart_settings(dialog, *, include_chart_appearance: bool = True) -> None:
    show_key, intensity_key, border_key = _box_style_keys(dialog)
    group = QGroupBox(tr("Background Box Settings"))
    layout = QVBoxLayout(group)

    dialog.glass_cb = QCheckBox(tr("Show Background Box"))
    dialog.glass_cb.setChecked(dialog.addon_config.get(show_key, True))
    layout.addWidget(dialog.glass_cb)

    def _activity_lines(lay):
        # the chart's lines: with the chart's look (they sat in the box's settings)
        dialog.avg_cb = QCheckBox(tr("Show Average Line"))
        dialog.avg_cb.setChecked(dialog.widget_def.get("show_average", True))
        lay.addWidget(dialog.avg_cb)
        dialog.cum_cb = QCheckBox(tr("Show Cumulative Line"))
        dialog.cum_cb.setChecked(dialog.widget_def.get("show_cumulative", True))
        lay.addWidget(dialog.cum_cb)

    if dialog.type == "activity" and not include_chart_appearance:
        _activity_lines(layout)

    from .web_glass import web_preview_on

    dialog.int_slider = SettingsSlider(
        tr("Background Opacity") if web_preview_on(dialog) else tr("Background Intensity"),
        dialog.addon_config.get(intensity_key, Config.DEFAULT_CONFIG[intensity_key]),
        0,
        100,
        suffix="%",
    )
    if web_preview_on(dialog):
        dialog.int_slider.setToolTip(tr("How much the box covers what is behind it: 0% see-through, 100% solid."))
    layout.addWidget(dialog.int_slider)

    dialog.border_slider = SettingsSlider(
        tr("Border Opacity"),
        dialog.addon_config.get(border_key, 50),
        0,
        100,
        suffix="%",
    )
    layout.addWidget(dialog.border_slider)

    # The web pinned widgets only (frosted glass, shadow): web_glass.py
    from .web_glass import add_web_glass

    if getattr(dialog, "type", None) == "text_label":
        add_web_glass(dialog, layout, "", Config.TEXT_WIDGET_GLASS_BLUR, Config.TEXT_WIDGET_GLASS_SHADOW)
    else:
        add_web_glass(dialog, layout, "", Config.PINNED_GLASS_BLUR, Config.PINNED_GLASS_SHADOW)

    # Like the stat cards' "Hover Effect": the border brightens on hover unless off.
    dialog.hover_border_cb = QCheckBox(tr("Show Hover Border"))
    dialog.hover_border_cb.setToolTip(tr("Brighten the box border when the mouse is over it."))
    _hk = _hover_border_key(dialog)
    dialog.hover_border_cb.setChecked(bool(dialog.addon_config.get(_hk, Config.DEFAULT_CONFIG.get(_hk, False))))
    layout.addWidget(dialog.hover_border_cb)
    dialog.content_layout.addWidget(group)

    if include_chart_appearance:
        # Chart appearance group - opacity applies to bars/slices/lines.
        opacity_defaults = {"card_counts": 100, "distribution": 100, "retention": 100}
        default_opacity = opacity_defaults.get(dialog.type, 100)
        appearance_group = QGroupBox(tr("Chart Appearance"))
        appearance_layout = QVBoxLayout(appearance_group)
        dialog.chart_opacity_slider = SettingsSlider(
            tr("Graph Opacity"),
            dialog.widget_def.get("chart_opacity", default_opacity),
            0,
            100,
            suffix="%",
        )
        appearance_layout.addWidget(dialog.chart_opacity_slider)
        if dialog.type == "activity":
            _activity_lines(appearance_layout)

        if dialog.type in ("card_counts", "todays_retention"):
            dialog.show_legend_cb = QCheckBox(tr("Show Legend"))
            dialog.show_legend_cb.setToolTip(tr("The list of card types with their counts, on the right of the donut. Off keeps only the donut."))
            dialog.show_legend_cb.setChecked(bool(dialog.widget_def.get("show_legend", True)))
            appearance_layout.addWidget(dialog.show_legend_cb)

            legend_row = QHBoxLayout()
            legend_row.addWidget(QLabel(tr("Legend Layout")))
            dialog.legend_mode_combo = QComboBox()
            for _label, _mode in ((tr("Auto"), "auto"), (tr("Always next to the donut"), "always"), (tr("On hover"), "hover")):
                dialog.legend_mode_combo.addItem(_label, _mode)
            _idx = dialog.legend_mode_combo.findData(dialog.widget_def.get("legend_mode", "auto"))
            dialog.legend_mode_combo.setCurrentIndex(max(0, _idx))
            dialog.legend_mode_combo.setToolTip(
                tr("Auto: the legend sits next to the donut when there is room to read it, "
                "otherwise the donut takes the whole space and a list icon shows the legend on hover.")
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
                tr("Total / Average Lines"),
                dialog.widget_def.get("line_opacity", _global_style("Chart_Line_Opacity")),
                0,
                200,
                suffix="%",
            )
            appearance_layout.addWidget(dialog.line_opacity_slider)
            if has_total_curve(dialog.type):
                # a clear line over the edge of the total's pale area (Settings > General > Chart Style's, or its own)
                dialog.total_line_slider = SettingsSlider(
                    tr("Total Line"),
                    dialog.widget_def.get("total_line", total_line_global(dialog)),
                    0,
                    100,
                    suffix="%",
                )
                dialog.total_line_slider.setToolTip(tr("A line over the edge of the Total area. 0% = no line (Anki's look), 100% = a clear line."))
                appearance_layout.addWidget(dialog.total_line_slider)
            dialog.bar_gradient_slider = SettingsSlider(
                tr("Bar Gradient"),
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
                ("show_grid_cb", "show_grid", Config.CHART_SHOW_GRID, tr("Grid Lines"),
                 tr("Horizontal guide lines behind this chart. Off keeps only the baseline.")),
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
                title=tr("Tooltip Lines"),
            )

        # (Interval Load and the card history charts have the same buttons as Review Intervals.)
        if dialog.type in ("future_due", "stability", "review_intervals", "interval_load",
                           "lapse_distribution", "review_distribution", "learning_steps", "time_distribution", "interval_history",
                           "stability_history"):
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
            range_group = QGroupBox(tr("Range Buttons"))
            _build_range_buttons_editor(dialog, range_group, "days" if dialog.type == "future_due" else "fsrs",
                                        choices, list(current))
            dialog.range_btn_group = range_group  # (scrolled to by "Edit Buttons...")
            dialog.content_layout.addWidget(range_group)



def _build_range_buttons_editor(dialog, group, kind, choices, values):
    """2 to 8 range buttons (a narrow header folds them into one button with a menu): a row
    per button, "-" to remove one, "+ Add Button" to add one. dialog.range_btn_combos is read
    on Save; dialog.range_btn_set_values(values) puts other values (Reset)."""
    from aqt.qt import QHBoxLayout, QPushButton, QVBoxLayout, QWidget
    from .range_button_row import RangeButtonRow
    from ....widgets.common.future_due_filters import MAX_BUTTONS, MIN_BUTTONS

    outer = QVBoxLayout(group)
    group.setProperty("noLiveUpdate", True)  # read on Save, as the rows themselves
    rows_box = QWidget(group)
    rows_lay = QVBoxLayout(rows_box)
    rows_lay.setContentsMargins(0, 0, 0, 0)
    outer.addWidget(rows_box)
    add_btn = QPushButton(tr("+ Add Button"), group)
    outer.addWidget(add_btn)
    dialog.range_btn_combos = []
    rows = []  # (row widget, combo)

    def refresh():
        for i, (row, _combo) in enumerate(rows):
            row.findChild(QLabel, "range_btn_label").setText(tr("Button {number}:", number=i + 1))
            row.findChild(QPushButton, "range_btn_remove").setEnabled(len(rows) > MIN_BUTTONS)
        add_btn.setEnabled(len(rows) < MAX_BUTTONS)
        dialog.range_btn_combos[:] = [c for _r, c in rows]

    def add_row(value):
        row = QWidget(rows_box)
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        label = QLabel("", row)
        label.setObjectName("range_btn_label")
        label.setMinimumWidth(80)
        lay.addWidget(label)
        combo = RangeButtonRow(kind, choices, value, parent=row)
        combo.setToolTip(tr("Pick different values, or Custom. They are shown in order, 'all' last."))
        lay.addWidget(combo, 1)
        rm = QPushButton(row)
        rm.setObjectName("range_btn_remove")
        # An icon: a "-" as text was squeezed out by the button's padding (an empty box).
        try:
            from aqt.qt import QSize

            from ...theme.icons import get_svg_icon

            rm.setIcon(get_svg_icon("x", size=14, context_ref=rm))
            rm.setIconSize(QSize(14, 14))
        except Exception:
            rm.setText("\u2715")
        rm.setFixedWidth(30)
        rm.setToolTip(tr("Remove this button"))
        lay.addWidget(rm)
        entry = (row, combo)
        rows.append(entry)
        rows_lay.addWidget(row)

        def remove(_c=False, e=entry):
            if len(rows) <= MIN_BUTTONS:
                return
            rows.remove(e)
            e[0].setParent(None)
            e[0].deleteLater()
            refresh()

        rm.clicked.connect(remove)
        refresh()

    def on_add(_c=False):
        if len(rows) >= MAX_BUTTONS:
            return
        used = {c.currentData() for _r, c in rows}
        free = next((d for d, _l in choices if d not in used), choices[0][0])
        add_row(free)

    def set_values(vals):
        for row, _c in list(rows):
            row.setParent(None)
            row.deleteLater()
        rows.clear()
        for v in vals:
            add_row(v)
        refresh()

    add_btn.clicked.connect(on_add)
    dialog.range_btn_set_values = set_values
    set_values(values)
