# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from __future__ import annotations

from aqt.qt import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    Qt,
    QVBoxLayout,
    QWidget,
)

from ... import Config
from .....config import is_dev_build
from .....dev_mode import open_data_folder, reset_everything, reset_profile
from .pinned_widgets_tab_builder import build_pinned_widgets_section


def _set_table_drawer_auto_close(parent_dialog, value):
    from ...details_dialog.table_drawer import set_auto_close

    set_auto_close(parent_dialog, value)


from .....qss import set_qss
from ....logic.logger import log_swallowed


def build_general_tab(dialog) -> None:
    gen_tab = QWidget(dialog.tabs_widget)
    gen_tab_layout = QVBoxLayout(gen_tab)
    gen_tab_layout.setContentsMargins(0, 0, 0, 0)

    gen_scroll = QScrollArea(gen_tab)
    gen_scroll.setWidgetResizable(True)
    gen_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    gen_scroll_content = QWidget()
    gen_scroll_content.setObjectName("scroll_content")
    gen_main_layout = QVBoxLayout(gen_scroll_content)
    gen_main_layout.setContentsMargins(15, 15, 15, 15)
    gen_main_layout.setSpacing(15)
    gen_scroll.setWidget(gen_scroll_content)
    gen_tab_layout.addWidget(gen_scroll)

    group_global = QGroupBox("Global Style")
    layout_global = QFormLayout(group_global)

    dialog.animation_scope_combo = QComboBox()
    dialog.animation_scope_combo.addItem("All Animations", "all")
    dialog.animation_scope_combo.addItem("No Pinned Animations", "no_pinned")
    dialog.animation_scope_combo.addItem("No Details Animations", "no_details")
    dialog.animation_scope_combo.addItem("No Animations", "none")
    dialog.animation_scope_combo.setToolTip(
        "Choose where animations are active: everywhere, only pinned off, only details off, or off globally."
    )
    dialog.animation_scope_combo.currentIndexChanged.connect(dialog.on_animation_scope_changed)
    layout_global.addRow("Animation Mode:", dialog.animation_scope_combo)

    dialog.chart_animation_threshold_spin = QSpinBox()
    dialog.chart_animation_threshold_spin.setRange(1, 24)
    chart_animation_threshold_tip = (
        "Maximum number of charts animating at once in a window.\n"
        "When more are ready together, the extra animations are queued.\n"
        "A single chart always animates right away. Lower this if the window lags."
    )
    dialog.chart_animation_threshold_spin.setToolTip(chart_animation_threshold_tip)
    dialog.chart_animation_threshold_spin.valueChanged.connect(dialog.on_chart_animation_threshold_changed)
    chart_animation_threshold_label = QLabel("Chart Animation Threshold:")
    chart_animation_threshold_label.setToolTip(chart_animation_threshold_tip)
    layout_global.addRow(chart_animation_threshold_label, dialog.chart_animation_threshold_spin)
    chart_animation_threshold_help = QLabel(
        "Extra chart animations are queued once this limit is reached."
    )
    chart_animation_threshold_help.setWordWrap(True)
    chart_animation_threshold_help.setToolTip(chart_animation_threshold_tip)
    set_qss(chart_animation_threshold_help, "color: rgba(127,127,127,0.95);")
    layout_global.addRow("", chart_animation_threshold_help)

    dialog.stats_precision_spin = QSpinBox()
    dialog.stats_precision_spin.setRange(0, 4)
    dialog.stats_precision_spin.setValue(
        dialog.parent_dialog.addon_config.config.get(Config.STATS_PRECISION, 2)
    )
    dialog.stats_precision_spin.valueChanged.connect(dialog.on_stats_precision_changed)
    dialog.stats_precision_spin.setToolTip("Decimals shown in stats, from 0 to 4. Trend arrows always show 1 decimal.")
    layout_global.addRow("Decimal Precision:", dialog.stats_precision_spin)

    dialog.thousands_separator_check = QCheckBox()
    dialog.thousands_separator_check.stateChanged.connect(dialog.on_thousands_separator_changed)
    layout_global.addRow("Thousands Separator (400,000):", dialog.thousands_separator_check)
    gen_main_layout.addWidget(group_global)

    group_display = QGroupBox("Deep Dive Display")
    layout_display = QFormLayout(group_display)

    dialog.adaptive_binning_check = QCheckBox()
    dialog.adaptive_binning_check.stateChanged.connect(dialog.on_adaptive_binning_changed)
    layout_display.addRow("Adaptive Chart Binning:", dialog.adaptive_binning_check)

    dialog.binning_scale_slider = QSlider(Qt.Orientation.Horizontal)
    dialog.binning_scale_slider.setRange(0, 4)
    dialog.binning_scale_slider.setSingleStep(1)
    dialog.binning_scale_slider.setPageStep(1)
    dialog.binning_scale_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    dialog.binning_scale_slider.setTickInterval(1)
    dialog.binning_scale_slider.setToolTip(
        "How many days are grouped in one bar when adaptive binning is enabled. "
        "Each step moves along day, 2 days, 3 days, week, 2 weeks, month, 2 months, 3 months."
    )
    dialog.binning_scale_value_lbl = QLabel("Normal")
    dialog.binning_scale_value_lbl.setMinimumWidth(80)
    from ...theme.icons import get_svg_icon

    dialog.binning_scale_reset_btn = QPushButton()
    dialog.binning_scale_reset_btn.setIcon(get_svg_icon("rotate-ccw", size=13))
    dialog.binning_scale_reset_btn.setFixedSize(22, 22)
    dialog.binning_scale_reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    dialog.binning_scale_reset_btn.setToolTip("Reset to default (Normal)")
    set_qss(dialog.binning_scale_reset_btn,
        "QPushButton { background: transparent; border: none; } "
        "QPushButton:hover { background: rgba(128,128,128,0.18); border-radius: 4px; }"
    )
    dialog.binning_scale_reset_btn.clicked.connect(lambda: dialog.binning_scale_slider.setValue(2))
    dialog.binning_scale_reset_btn.setVisible(False)
    binning_row = QWidget()
    binning_row_lay = QHBoxLayout(binning_row)
    binning_row_lay.setContentsMargins(0, 0, 0, 0)
    binning_row_lay.setSpacing(8)
    binning_row_lay.addWidget(dialog.binning_scale_slider, 1)
    binning_row_lay.addWidget(dialog.binning_scale_value_lbl, 0)
    binning_row_lay.addWidget(dialog.binning_scale_reset_btn, 0)
    dialog.binning_scale_slider.valueChanged.connect(dialog.on_binning_scale_changed)

    def _sync_binning_scale_enabled(checked):
        dialog.binning_scale_slider.setEnabled(bool(checked))
        dialog.binning_scale_reset_btn.setEnabled(bool(checked))

    dialog.adaptive_binning_check.toggled.connect(_sync_binning_scale_enabled)
    layout_display.addRow("Chart Binning:", binning_row)

    dialog.side_view_check = QCheckBox()
    dialog.side_view_check.setToolTip(
        "Off: the table slides up from the bottom of the window. On: it slides in from the right edge."
    )
    dialog.side_view_check.stateChanged.connect(dialog.on_side_view_changed)
    layout_display.addRow("Table On The Side:", dialog.side_view_check)

    dialog.table_drawer_auto_check = QCheckBox()
    dialog.table_drawer_auto_check.setToolTip(
        "When the table drawer is on, close the table after you pick a deck in it."
    )
    dialog.table_drawer_auto_check.stateChanged.connect(
        lambda state, d=dialog: _set_table_drawer_auto_close(d.parent_dialog, bool(state))
    )
    layout_display.addRow("Close Table After Picking:", dialog.table_drawer_auto_check)

    from aqt.qt import QKeySequence as _QKeySequence, QKeySequenceEdit as _QKeySequenceEdit

    drawer_key_box = QWidget()
    drawer_key_row = QHBoxLayout(drawer_key_box)
    drawer_key_row.setContentsMargins(0, 0, 0, 0)
    dialog.table_drawer_key_edit = _QKeySequenceEdit()
    dialog.table_drawer_key_edit.setToolTip("Key that opens or closes the table in the Deep Dive window.")
    dialog.table_drawer_key_edit.setKeySequence(
        _QKeySequence(str(dialog.parent_dialog.addon_config.config.get(Config.DETAILS_TABLE_DRAWER_SHORTCUT, "T") or ""))
    )
    drawer_key_clear = QPushButton("Clear")
    drawer_key_row.addWidget(dialog.table_drawer_key_edit, 1)
    drawer_key_row.addWidget(drawer_key_clear)
    layout_display.addRow("Table Shortcut:", drawer_key_box)

    def _on_drawer_key_changed(seq):
        from ...details_dialog.table_drawer import apply_shortcut

        # One key combination only.
        full = seq.toString(_QKeySequence.SequenceFormat.PortableText)
        text = full.split(",")[0].strip()
        if text != full:
            dialog.table_drawer_key_edit.blockSignals(True)
            dialog.table_drawer_key_edit.setKeySequence(_QKeySequence(text))
            dialog.table_drawer_key_edit.blockSignals(False)
        dialog.parent_dialog.addon_config.config[Config.DETAILS_TABLE_DRAWER_SHORTCUT] = text
        try:
            dialog.parent_dialog.addon_config.write_config_vals({Config.DETAILS_TABLE_DRAWER_SHORTCUT: text})
        except Exception:
            log_swallowed()
        apply_shortcut(dialog.parent_dialog, text)

    dialog.table_drawer_key_edit.keySequenceChanged.connect(_on_drawer_key_changed)
    drawer_key_clear.clicked.connect(lambda: dialog.table_drawer_key_edit.setKeySequence(_QKeySequence()))

    dialog.show_empty_charts_check = QCheckBox()
    dialog.show_empty_charts_check.setToolTip(
        "Off: Deep Dive leaves out charts that have no data for the selected deck and period. "
        "On: they stay, with a \"No data for this graph\" message."
    )

    def _on_show_empty_charts_toggled(checked):
        conf = dialog.parent_dialog.addon_config
        if bool(conf.config.get(Config.SHOW_EMPTY_CHARTS, False)) == bool(checked):
            return
        conf.config[Config.SHOW_EMPTY_CHARTS] = bool(checked)
        try:
            conf.set_value(Config.SHOW_EMPTY_CHARTS, bool(checked))
        except Exception:
            log_swallowed()
        mgr = getattr(dialog.parent_dialog, "deep_dive_manager", None)
        if mgr is not None:
            try:
                from aqt.qt import QTimer as _QTimer

                _QTimer.singleShot(0, mgr._populate_dashboard)
            except Exception:
                log_swallowed()

    dialog.show_empty_charts_check.toggled.connect(_on_show_empty_charts_toggled)
    layout_display.addRow("Show Charts Without Data:", dialog.show_empty_charts_check)

    dialog.dd_collapsible_check = QCheckBox()
    dialog.dd_collapsible_check.setToolTip(
        "Adds an arrow to each Deep Dive chart so it can be folded to its title. "
        "Off: the arrows are hidden and every chart stays open."
    )

    def _on_dd_collapsible_toggled(checked):
        conf = dialog.parent_dialog.addon_config
        if bool(conf.config.get(Config.DEEP_DIVE_CHARTS_COLLAPSIBLE, True)) == bool(checked):
            return
        conf.config[Config.DEEP_DIVE_CHARTS_COLLAPSIBLE] = bool(checked)
        try:
            conf.set_value(Config.DEEP_DIVE_CHARTS_COLLAPSIBLE, bool(checked))
        except Exception:
            log_swallowed()
        mgr = getattr(dialog.parent_dialog, "deep_dive_manager", None)
        if mgr is not None:
            try:
                from aqt.qt import QTimer as _QTimer

                _QTimer.singleShot(0, mgr._populate_dashboard)
            except Exception:
                log_swallowed()

    dialog.dd_collapsible_check.toggled.connect(_on_dd_collapsible_toggled)
    layout_display.addRow("Collapsible Charts:", dialog.dd_collapsible_check)

    def _bool_setting(key, checked):
        conf = dialog.parent_dialog.addon_config
        conf.config[key] = bool(checked)
        try:
            conf.set_value(key, bool(checked))
        except Exception:
            log_swallowed()

    dialog.dd_fill_height_check = QCheckBox()
    dialog.dd_fill_height_check.setToolTip(
        "When the Deep Dive charts do not fill the window, make them taller (up to 1.6x) "
        "so there is no empty space under them. Charts you resized by hand are left alone."
    )

    def _on_fill_height_toggled(checked):
        _bool_setting(Config.DEEP_DIVE_FILL_HEIGHT, checked)
        mgr = getattr(dialog.parent_dialog, "deep_dive_manager", None)
        if mgr is not None:
            try:
                from ...deep_dive.layout_parts.fill_height import update as _fill_update

                _fill_update(mgr)
            except Exception:
                log_swallowed()

    dialog.dd_fill_height_check.toggled.connect(_on_fill_height_toggled)
    layout_display.addRow("Fill Window Height:", dialog.dd_fill_height_check)
    gen_main_layout.addWidget(group_display)

    group_chart_style = QGroupBox("Chart Style")
    layout_chart_style = QFormLayout(group_chart_style)

    def _style_slider(config_key, low, high, tip):
        conf = dialog.parent_dialog.addon_config.config
        _style_default = int(Config.DEFAULT_CONFIG.get(config_key, 100))
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(low, high)
        slider.setPageStep(5)
        slider.setToolTip(tip)
        value_lbl = QLabel("")
        value_lbl.setMinimumWidth(48)
        try:
            slider.setValue(int(conf.get(config_key, _style_default)))
        except Exception:
            slider.setValue(_style_default)
        value_lbl.setText(f"{slider.value()}%")

        def _changed(v, _k=config_key, _lbl=value_lbl):
            _lbl.setText(f"{v}%")
            conf[_k] = int(v)
            _repaint_charts()

        slider.valueChanged.connect(_changed)
        row = QWidget()
        row_lay = QHBoxLayout(row)
        row_lay.setContentsMargins(0, 0, 0, 0)
        row_lay.setSpacing(8)
        row_lay.addWidget(slider, 1)
        row_lay.addWidget(value_lbl, 0)
        return slider, value_lbl, row

    dialog.chart_line_opacity_slider, dialog.chart_line_opacity_lbl, _line_row = _style_slider(
        Config.CHART_LINE_OPACITY, 0, 200,
        "Opacity of the Total and Average lines (and the soft area under Total). Lower = more discreet.",
    )
    layout_chart_style.addRow("Total / Average Lines:", _line_row)
    dialog.chart_bar_gradient_slider, dialog.chart_bar_gradient_lbl, _grad_row = _style_slider(
        Config.CHART_BAR_GRADIENT, 0, 100,
        "Strength of the soft fade on bars. 0% = flat bars, 100% = default.",
    )
    layout_chart_style.addRow("Bar Gradient:", _grad_row)

    def _style_check(config_key, text, tip):
        conf = dialog.parent_dialog.addon_config.config
        check = QCheckBox(text)
        check.setToolTip(tip)
        check.setChecked(bool(conf.get(config_key, True)))

        def _toggled(on, _k=config_key):
            conf[_k] = bool(on)
            _repaint_charts()

        check.toggled.connect(_toggled)
        return check

    def _repaint_charts():
        # Charts re-read the style once a second; force the refresh now.
        try:
            from ....widgets.chart_utils import drawing as _drawing

            _drawing._STYLE_CACHE[0] = 0.0
        except Exception:
            log_swallowed()
        try:
            from aqt import mw

            for w in (mw.app.topLevelWidgets() if mw and mw.app else []):
                w.update()
                for child in w.findChildren(QWidget):
                    child.update()
        except Exception:
            log_swallowed()

    dialog.chart_show_grid_check = _style_check(
        Config.CHART_SHOW_GRID,
        "Grid lines",
        "Horizontal guide lines behind the charts. Off keeps only the baseline.",
    )
    layout_chart_style.addRow("", dialog.chart_show_grid_check)
    gen_main_layout.addWidget(group_chart_style)

    group_table = QGroupBox("Table Layout")
    layout_table = QFormLayout(group_table)
    dialog.global_row_height_spin = QSpinBox()
    dialog.global_row_height_spin.setRange(10, 200)
    global_row_h = dialog.parent_dialog.addon_config.config.get(Config.GLOBAL_ROW_HEIGHT, 30)
    dialog.global_row_height_spin.setValue(global_row_h)
    dialog.global_row_height_spin.valueChanged.connect(dialog.on_global_row_height_changed)
    layout_table.addRow("Row Height (px):", dialog.global_row_height_spin)
    dialog.table_zebra_check = QCheckBox("Alternate row shading")
    dialog.table_zebra_check.setToolTip("Zebra striping: every other row in the tables is slightly shaded.")
    dialog.table_zebra_check.setChecked(bool(dialog.parent_dialog.addon_config.config.get(Config.TABLE_ZEBRA, True)))

    def _zebra_toggled(on):
        dialog.parent_dialog.addon_config.config[Config.TABLE_ZEBRA] = bool(on)
        from ....ui.table.zebra import apply_zebra_to_dialog_tables

        apply_zebra_to_dialog_tables(dialog.parent_dialog, on)

    dialog.table_zebra_check.toggled.connect(_zebra_toggled)
    layout_table.addRow("Zebra Rows:", dialog.table_zebra_check)
    gen_main_layout.addWidget(group_table)

    group_toolbar = QGroupBox("Anki Toolbar")
    layout_toolbar = QFormLayout(group_toolbar)
    dialog.toolbar_style_combo = QComboBox()
    dialog.toolbar_style_combo.addItem("Logo", Config.TOOLBAR_STYLE_LOGO)
    dialog.toolbar_style_combo.addItem("Text (Deep Dive)", Config.TOOLBAR_STYLE_TEXT)
    dialog.toolbar_style_combo.addItem("None (Hidden)", Config.TOOLBAR_STYLE_NONE)
    dialog.toolbar_style_combo.currentIndexChanged.connect(dialog.on_toolbar_button_style_changed)
    layout_toolbar.addRow("Toolbar Button:", dialog.toolbar_style_combo)
    # Custom label, only shown for the "Text" style.
    dialog.toolbar_text_edit = QLineEdit()
    dialog.toolbar_text_edit.setPlaceholderText("Deep Dive")
    dialog.toolbar_text_edit.setMaxLength(40)
    dialog.toolbar_text_edit.setText(
        str(dialog.parent_dialog.addon_config.config.get(Config.TOOLBAR_BUTTON_TEXT, "Deep Dive") or "")
    )
    dialog.toolbar_text_edit.textChanged.connect(
        lambda text: dialog.parent_dialog.addon_config.config.__setitem__(Config.TOOLBAR_BUTTON_TEXT, text)
    )
    layout_toolbar.addRow("Button Text:", dialog.toolbar_text_edit)
    dialog._toolbar_form = layout_toolbar

    from aqt import mw
    from aqt.qt import QAction, QKeySequence, QKeySequenceEdit

    shortcut_box = QWidget()
    shortcut_row = QHBoxLayout(shortcut_box)
    shortcut_row.setContentsMargins(0, 0, 0, 0)
    dialog.open_shortcut_edit = QKeySequenceEdit()
    dialog.open_shortcut_edit.setKeySequence(
        QKeySequence(str(dialog.parent_dialog.addon_config.config.get(Config.OPEN_SHORTCUT, "") or ""))
    )
    shortcut_clear = QPushButton("Clear")
    shortcut_row.addWidget(dialog.open_shortcut_edit, 1)
    shortcut_row.addWidget(shortcut_clear)
    layout_toolbar.addRow("Open Shortcut:", shortcut_box)
    dialog.open_shortcut_hint = QLabel()
    dialog.open_shortcut_hint.setVisible(False)
    layout_toolbar.addRow("", dialog.open_shortcut_hint)

    def _shortcut_conflict(text):
        if not text:
            return ""
        mine = getattr(mw, "_deep_dive_open_action", None)
        for act in mw.findChildren(QAction):
            if act is mine:
                continue
            for key in act.shortcuts():
                if key.toString(QKeySequence.SequenceFormat.PortableText) == text:
                    return act.text().replace("&", "").split("\t")[0].strip()
        return ""

    def _on_shortcut_changed(seq):
        # One key combination only.
        text = seq.toString(QKeySequence.SequenceFormat.PortableText).split(",")[0].strip()
        if text != seq.toString(QKeySequence.SequenceFormat.PortableText):
            dialog.open_shortcut_edit.blockSignals(True)
            dialog.open_shortcut_edit.setKeySequence(QKeySequence(text))
            dialog.open_shortcut_edit.blockSignals(False)
        dialog.parent_dialog.addon_config.config[Config.OPEN_SHORTCUT] = text
        used = _shortcut_conflict(text)
        dialog.open_shortcut_hint.setText(f"Already used by Anki: {used}" if used else "")
        dialog.open_shortcut_hint.setVisible(bool(used))

    dialog.open_shortcut_edit.keySequenceChanged.connect(_on_shortcut_changed)
    shortcut_clear.clicked.connect(lambda: dialog.open_shortcut_edit.setKeySequence(QKeySequence()))
    _style = dialog.parent_dialog.addon_config.config.get(Config.TOOLBAR_BUTTON_STYLE, Config.TOOLBAR_STYLE_LOGO)
    if not dialog.parent_dialog.addon_config.config.get(Config.SHOW_TOP_TOOLBAR_BUTTON, True):
        _style = Config.TOOLBAR_STYLE_NONE
    _style_idx = dialog.toolbar_style_combo.findData(_style)
    if _style_idx >= 0:
        dialog.toolbar_style_combo.blockSignals(True)
        dialog.toolbar_style_combo.setCurrentIndex(_style_idx)
        dialog.toolbar_style_combo.blockSignals(False)
    from ..shared.dialog_runtime_handlers import sync_toolbar_text_row

    sync_toolbar_text_row(dialog)
    gen_main_layout.addWidget(group_toolbar)

    build_pinned_widgets_section(dialog, gen_main_layout)

    # Tools for working on the add-on itself, only in a source checkout.
    if is_dev_build():
        group_dev = QGroupBox("Developer")
        layout_dev = QVBoxLayout(group_dev)
        try:
            from ... import get_color

            _danger = str(get_color(dialog.addon_config, Config.COLOR_AGAIN, dialog))
        except Exception:
            _danger = "#ef4444"
        _danger_qss = (
            f"QPushButton {{ color: {_danger}; border: 1px solid {_danger}; border-radius: 4px; padding: 4px 10px; }}"
            f"QPushButton:hover {{ background-color: {_danger}; color: white; }}"
        )

        def _close_without_saving(d):
            # Close this window and Deep Dive without saving, otherwise the old values would be
            # written back into the settings that were just reset.
            from aqt.qt import QTimer

            d._cancel_restored = True
            parent = getattr(d, "parent_dialog", None)

            def _close():
                d.reject()
                if parent is not None:
                    parent._skip_state_save = True
                    parent.close()

            QTimer.singleShot(0, _close)

        def _confirm_and_reset(d, action, text, title, done_text):
            from aqt.utils import askUser, tooltip

            if not askUser(text, parent=d, defaultno=True, title=title):
                return
            action()
            _close_without_saving(d)
            tooltip(done_text, period=4000)

        def _on_reset_profile(_checked=False, d=dialog):
            _confirm_and_reset(
                d,
                reset_profile,
                "This deletes the Deep Dive settings of the current Anki profile (pinned widgets, "
                "colors, excluded dates, everything) and cannot be undone.\n\nContinue?",
                "Reset this profile",
                "Deep Dive: settings of this profile reset. Reopen the Deep Dive window.",
            )

        def _on_reset_everything(_checked=False, d=dialog):
            _confirm_and_reset(
                d,
                reset_everything,
                "This deletes the Deep Dive settings of every Anki profile (pinned widgets, "
                "colors, excluded dates, everything) and cannot be undone.\n\nContinue?",
                "Reset all profiles",
                "Deep Dive: settings of all profiles reset. Reopen the Deep Dive window.",
            )

        dialog.reset_profile_btn = QPushButton("Reset this profile's settings...")
        set_qss(dialog.reset_profile_btn, _danger_qss)
        dialog.reset_profile_btn.setToolTip("Deletes the saved settings of the current Anki profile only.")
        dialog.reset_profile_btn.clicked.connect(_on_reset_profile)

        dialog.reset_everything_btn = QPushButton("Reset all profiles...")
        set_qss(dialog.reset_everything_btn, _danger_qss)
        dialog.reset_everything_btn.setToolTip(
            "Deletes the saved settings of all Anki profiles, as if the add-on was just installed."
        )
        dialog.reset_everything_btn.clicked.connect(_on_reset_everything)

        dialog.open_data_folder_btn = QPushButton("Open data folder")
        dialog.open_data_folder_btn.setToolTip("Opens user_files: settings, history cache and the debug log.")
        dialog.open_data_folder_btn.clicked.connect(lambda _checked=False: open_data_folder())

        _dev_row = QHBoxLayout()
        _dev_row.addWidget(dialog.reset_profile_btn)
        _dev_row.addWidget(dialog.reset_everything_btn)
        layout_dev.addLayout(_dev_row)
        layout_dev.addWidget(dialog.open_data_folder_btn)
        gen_main_layout.addWidget(group_dev)

    gen_main_layout.addStretch()
    dialog.tabs_widget.addTab(gen_tab, "General")

