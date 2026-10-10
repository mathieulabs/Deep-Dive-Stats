# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

import copy
from aqt import mw
from aqt.qt import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    QGroupBox,
    QFormLayout,
    QCheckBox,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QSlider,
    QScrollArea,
    QTimer,
)
from aqt.theme import theme_manager
from ... import COLOR_DEFAULTS, Config, ThemePalettes, get_color
from ....logic.logger import log_swallowed
from ....widgets.stats_cards.logic.model import get_stat_card_default_title
from ...theme.icons import get_svg_icon
from ...theme import get_settings_dialog_style, get_theme_palette, get_theme_effective_is_dark
from ..widgets.persistence_keys import (
    DEEP_DIVE_STYLE_MARKER_KEYS,
    WIDGET_BEHAVIOR_KEYS,
)
from ..widgets.live_config_writes import (
    apply_activity_live_changes,
    apply_chart_opacity_live_change,
    apply_generic_chart_live_changes,
    apply_heatmap_live_changes,
    apply_stat_card_live_changes,
    apply_text_label_live_changes,
)
from ..widgets.facecard_section import setup_facecard_settings
from ..widgets.chart_section import setup_chart_settings
from ..widgets.heatmap_section import setup_heatmap_settings
from ..widgets.heatmap_reset import reset_heatmap
from ..widgets.heatmap_color import (
    reset_color,
    select_color,
    update_color_button,
)
from ..widgets.chart_reset import reset_chart_settings
from ..widgets.label_defaults import (
    get_default_label,
    reset_label,
    update_reset_button_visibility as update_label_reset_button_visibility,
)
from ..widgets.save_persistence import persist_widget_settings
from ..shared import apply_standard_dialog_sizing, clamp_dialog_height, clamp_dialog_width, install_no_wheel_filters
from .....qss import set_qss
from .....config import ConfigManager, set_live_config_override

class WidgetSettingsDialog(QDialog):
    """A focused dialog for configuring a specific pinned or deep dive widget."""
    
    def __init__(self, widget_def, parent=None, global_config=None, local_config=None, theme_config=None):
        super().__init__(parent)
        self.widget_def = widget_def
        self.widget_id = widget_def.get("id")
        self.type = widget_def.get("type")
        
        if global_config is not None:
             self.global_config = global_config
        else:
             self.global_config = ConfigManager(mw).config
             
        # Local config defaults to the widget definition
        self.local_config = local_config if local_config is not None else self.widget_def
        
        self.is_unlinked = self.local_config.get("use_custom_style", False)
        self.is_grid = widget_def.get("is_grid", False)
        
        self.addon_config = self.local_config if self.is_unlinked else self.global_config

        # Theme source can differ from style source (e.g. Deep Dive grid widget settings
        # stores style overrides in a compact dict). Keep a full config dict for theming.
        self.theme_config = theme_config if isinstance(theme_config, dict) else None
        if self.theme_config is None:
            p = parent
            while p is not None:
                cfg_obj = getattr(p, "addon_config", None)
                cfg_dict = getattr(cfg_obj, "config", None)
                if isinstance(cfg_dict, dict):
                    self.theme_config = cfg_dict
                    break
                if isinstance(cfg_obj, dict):
                    self.theme_config = cfg_obj
                    break
                p = p.parentWidget() if hasattr(p, "parentWidget") else None
        if self.theme_config is None and isinstance(self.global_config, dict):
            self.theme_config = self.global_config
        # Deep Dive heatmap: the chart reads the top-level config when the compact
        # grid style has no value, so show those values in the dialog too.
        if (
            self.is_grid
            and widget_def.get("type") == "heatmap"
            and isinstance(self.theme_config, dict)
            and self.theme_config is not self.global_config
            and isinstance(self.global_config, dict)
        ):
            for _k, _v in self.theme_config.items():
                if isinstance(_k, str) and _k.startswith("Heatmap_") and _k not in self.global_config:
                    self.global_config[_k] = _v
        # Opened from a pinned widget: use the pinned theme, which can differ
        # from the Deep Dive one.
        if theme_config is None and isinstance(self.theme_config, dict):
            try:
                from ....widgets.chart_utils.theme import get_context_theme_config

                self.theme_config = get_context_theme_config(parent, self.theme_config)
            except Exception:
                log_swallowed()
        
        self.is_dashboard_context = False
        if hasattr(parent, "is_pinned") and not parent.is_pinned:
            self.is_dashboard_context = True
        elif hasattr(parent, "cards"):
            try:
                cards = list(getattr(parent, "cards", []) or [])
                if cards and not any(bool(getattr(c, "is_pinned", False)) for c in cards):
                    self.is_dashboard_context = True
            except Exception:
                log_swallowed()

        # Pinned mode when global_config holds Pinned_Widgets. The dashboard context stays isolated from pinned persistence.
        self.is_pinned_mode = ("Pinned_Widgets" in self.global_config) and not self.is_dashboard_context
        
        # Charts re-read their colours from the config while this dialog is
        # open; let them see the unsaved edits (see read_config_dict).
        if isinstance(self.global_config, dict):
            set_live_config_override(self.global_config)

        self._backup_global = copy.deepcopy(self.global_config)
        self._backup_local = copy.deepcopy(self.local_config)
        self._backup_unlinked = self.is_unlinked
        
        # Debounce timer for live updates
        self.update_timer = QTimer(self)
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self.apply_live_changes)
        
        self.setWindowTitle(f"Configure Widget: {self.type.replace('_', ' ').title()}")
        
        apply_standard_dialog_sizing(self, min_width=500)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll_content = QWidget(self.scroll)
        self.scroll_content.setObjectName("scroll_content")
        self.content_layout = QVBoxLayout(self.scroll_content)
        self.content_layout.setContentsMargins(20, 20, 20, 10)
        self.content_layout.setSpacing(15)
        self.scroll.setWidget(self.scroll_content)
        self.main_layout.addWidget(self.scroll)
        
        self.unlink_cb = QCheckBox("Unlink settings (Separate from other widgets)")
        self.unlink_cb.setChecked(self.is_unlinked)
        self.unlink_cb.toggled.connect(self.toggle_unlink)
        # Heatmap settings do not use the unlink concept
        if self.type == "heatmap":
            self.unlink_cb.setVisible(False)
        self.content_layout.addWidget(self.unlink_cb)
        
        if self.type != "text_label":
            group_gen = QGroupBox("General")
            layout_gen = QFormLayout(group_gen)
            
            label_row = QHBoxLayout()
            self.label_edit = QLineEdit(widget_def.get("label", ""))
            self.label_edit.setPlaceholderText("Empty = no title")
            self.label_edit.textChanged.connect(self._update_reset_button_visibility)
            label_row.addWidget(self.label_edit)
            
            self.reset_label_btn = QPushButton()
            self.reset_label_btn.setIcon(get_svg_icon("rotate-ccw", size=14, context_ref=self))
            self.reset_label_btn.setFixedSize(24, 24)
            self.reset_label_btn.setToolTip("Reset to Default")
            set_qss(self.reset_label_btn, "QPushButton { background: transparent; border: none; } QPushButton:hover { background: rgba(128,128,128,0.18); border-radius: 4px; }")
            self.reset_label_btn.clicked.connect(self._reset_label)
            label_row.addWidget(self.reset_label_btn)
            
            layout_gen.addRow("Display Label:", label_row)
            
            if self.type == "stat_card" and not self.is_dashboard_context:
                 self.stat_key_combo = QComboBox()
                 found_keys = []
                 for k in Config.DEFAULT_CONFIG:
                     if k.startswith("Dash_Show_"):
                         label = get_stat_card_default_title(k)
                         self.stat_key_combo.addItem(label, k)
                         found_keys.append(k)
                 
                 current_key = widget_def.get("stat_key")
                 idx = self.stat_key_combo.findData(current_key)
                 if idx >= 0:
                     self.stat_key_combo.setCurrentIndex(idx)
                 
                 self.stat_key_combo.currentIndexChanged.connect(self._update_reset_button_visibility)
                 layout_gen.addRow("Metric:", self.stat_key_combo)

                 from ....widgets.pinned.widget_factory.builders.time_units import UNIT_CHOICES
                 from ....widgets.pinned.widget_factory.builders.stat_card import TIME_STAT_FIELDS
                 self.time_unit_combo = QComboBox()
                 for _val, _label in UNIT_CHOICES:
                     self.time_unit_combo.addItem(_label, _val)
                 _ti = self.time_unit_combo.findData(widget_def.get("time_unit", "auto"))
                 self.time_unit_combo.setCurrentIndex(_ti if _ti >= 0 else 0)
                 self.time_unit_combo.setToolTip("Auto: minutes under 1 hour, hours above (as before).\nOr force seconds, minutes, hours or days.")
                 self.time_unit_label = QLabel("Time unit:")
                 layout_gen.addRow(self.time_unit_label, self.time_unit_combo)

                 def _sync_time_unit_row(*_a, _combo=self.stat_key_combo):
                     is_time = _combo.currentData() in TIME_STAT_FIELDS
                     self.time_unit_combo.setVisible(is_time)
                     self.time_unit_label.setVisible(is_time)
                 self.stat_key_combo.currentIndexChanged.connect(_sync_time_unit_row)
                 _sync_time_unit_row()

            self._update_reset_button_visibility()

            self.content_layout.addWidget(group_gen)
        
        if self.type == "text_label":
            self._setup_text_label_settings()
        elif self.type == "stat_card":
            self._setup_facecard_settings()
        elif self.type == "heatmap":
            self._setup_heatmap_settings()
        else:
            self._setup_chart_settings()
            
        self.bottom_area = QWidget(self)
        bottom_area_layout = QVBoxLayout(self.bottom_area)
        bottom_area_layout.setContentsMargins(20, 10, 20, 20)
        
        btn_layout = QHBoxLayout()

        if self.type not in ("stat_card", "text_label"):
            _reset_handler = self._reset_heatmap if self.type == "heatmap" else self._reset_chart_settings
            self.reset_btn = QPushButton(" Reset to Defaults")
            self.reset_btn.setIcon(get_svg_icon("rotate-ccw", size=14, context_ref=self))
            self.reset_btn.setMinimumHeight(28)
            self.reset_btn.clicked.connect(_reset_handler)
            btn_layout.addWidget(self.reset_btn)

        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.ok_btn = QPushButton("Save")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self.save_and_close)

        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.ok_btn)
        bottom_area_layout.addLayout(btn_layout)
        self.main_layout.addWidget(self.bottom_area)
        
        self.refresh_styles()
        self._install_wheel_filters()
        self._connect_live_updates()
        
        # Manual resize: content + footer + padding. Process events first so size hints are up to date.
        from aqt.qt import QCoreApplication
        QCoreApplication.processEvents()
        
        content_h = self.scroll_content.sizeHint().height()
        content_w = max(
            self.scroll_content.sizeHint().width(),
            self.scroll_content.minimumSizeHint().width(),
            self.bottom_area.sizeHint().width(),
        )
        footer_h = self.bottom_area.sizeHint().height()
        total_h = content_h + footer_h + 10 # small buffer
        total_w = content_w + 56 # scroll area + dialog margins
        
        final_h = clamp_dialog_height(self.maximumHeight(), total_h)
        final_w = clamp_dialog_width(total_w, min_width=500)
        self.resize(final_w, final_h)

    def done(self, result):
        self.update_timer.stop()
        set_live_config_override(None)
        super().done(result)

    def reject(self):
        """Restore original config state and refresh UI before closing."""
        self.global_config.clear()
        self.global_config.update(self._backup_global)
        
        self.local_config.clear()
        self.local_config.update(self._backup_local)
        
        self.is_unlinked = self._backup_unlinked
        self.addon_config = self.local_config if self.is_unlinked else self.global_config
        
        # Refresh the UI widgets to the restored config first, so apply_live_changes does not read the modified values.
        try:
            self.refresh_ui_values()
            self.apply_live_changes()
        except Exception:
            log_swallowed()
        finally:
            super().reject()

    def _install_wheel_filters(self):
        """Install event filters to disable wheel on input widgets."""
        install_no_wheel_filters(self, (QComboBox, QSpinBox, QSlider))

    def _connect_live_updates(self):
        """Connect all interactive elements to live update logic."""
        if hasattr(self, "label_edit"):
            self.label_edit.textChanged.connect(lambda *_a: self._trigger_live_update())

        def _live_handler(control):
            # sender() is not reliable for plain callables, so the control is bound here.
            def _changed(*_args):
                self._pending_inplace = self._is_inplace_control(control)
                self.apply_live_changes()
            return _changed

        for cb in self.findChildren(QCheckBox):
            if cb == self.unlink_cb: continue # Managed separately
            cb.stateChanged.connect(_live_handler(cb))
        
        def _debounced_handler(control):
            def _changed(*_args):
                self._trigger_live_update(control)
            return _changed

        for slider in self.findChildren(QSlider):
            slider.valueChanged.connect(_debounced_handler(slider))
            
        # Combo boxes apply directly, no debounce needed
        def _pending_only(w):
            p = w.parentWidget()
            return p is not None and bool(p.property("noLiveUpdate"))

        for combo in self.findChildren(QComboBox):
            if hasattr(self, "stat_key_combo") and combo == self.stat_key_combo: continue
            if _pending_only(combo): continue

            combo.currentIndexChanged.connect(_live_handler(combo))
            
        for spin in self.findChildren(QSpinBox):
            if _pending_only(spin): continue
            spin.valueChanged.connect(_debounced_handler(spin))

    def _trigger_live_update(self, control=None):
        """Restart debouncing timer to avoid excessive re-renders."""
        # 50ms is enough to be imperceptible but prevents 60+ FPS re-renders
        self._pending_inplace = self._is_inplace_control(control)
        self.update_timer.start(50)

    def _is_inplace_control(self, control):
        """True for controls whose effect apply_live_changes already applies to the chart itself.

        Those need no dashboard rebuild, which would also destroy this dialog (it is a child of the chart)."""
        names = (
            "chart_opacity_slider", "line_opacity_slider", "bar_gradient_slider",
            "show_grid_cb", "show_legend_cb", "legend_mode_combo",
        )
        owners = [getattr(self, n, None) for n in names]
        owners += list((getattr(self, "tooltip_checks", None) or {}).values())
        owners = [o for o in owners if o is not None]
        node = control
        for _ in range(3):
            if node is None:
                return False
            if any(node is o for o in owners):
                return True
            node = node.parentWidget() if hasattr(node, "parentWidget") else None
        return False

    def toggle_unlink(self, checked):
        """Switch between Global and Local config context."""
        self.is_unlinked = checked
        
        if self.is_unlinked:
            self.addon_config = self.local_config
            # Copy current global values to local where missing, for a smooth transition.
            for k, v in self.global_config.items():
                if k not in self.local_config and isinstance(k, str) and k.startswith(("Pinned_", "Facecards_", "Heatmap_", "Dashboard_", "Text_")):
                    self.local_config[k] = v
        else:
            self.addon_config = self.global_config
            
        self.refresh_ui_values()
        
        self.apply_live_changes()

    def refresh_ui_values(self):
        """Reload UI values from the current self.addon_config."""
        conf = self.addon_config
        
        def set_val(obj, method, val):
            obj.blockSignals(True)
            getattr(obj, method)(val)
            obj.blockSignals(False)

        if self.type == "text_label":
            if hasattr(self, "_tl_editor"):
                self._tl_editor.set_template(self.widget_def.get("template", ""))
            if hasattr(self, "glass_cb"): set_val(self.glass_cb, "setChecked", conf.get(Config.TEXT_WIDGET_SHOW_GLASS, True))
            if hasattr(self, "int_slider"): set_val(self.int_slider, "setValue", conf.get(Config.TEXT_WIDGET_GLASS_INTENSITY, 20))
            if hasattr(self, "border_slider"): set_val(self.border_slider, "setValue", conf.get(Config.TEXT_WIDGET_GLASS_BORDER, 50))
            if hasattr(self, "hover_border_cb"): set_val(self.hover_border_cb, "setChecked", conf.get(Config.TEXT_WIDGET_HOVER_BORDER, True))
        elif self.type == "stat_card":
            if hasattr(self, "scale_spin"): set_val(self.scale_spin, "setValue", conf.get(self._get_key(Config.FACECARDS_SCALE, Config.DASHBOARD_SCALE), 100))
            if hasattr(self, "title_size_slider"): set_val(self.title_size_slider, "setValue", conf.get(self._get_key(Config.FACECARDS_TITLE_SIZE, Config.DASHBOARD_TITLE_SIZE), 100))
            if hasattr(self, "title_color"):
                self.title_color = str(conf.get(self._get_key(Config.FACECARDS_TITLE_COLOR, Config.DASHBOARD_TITLE_COLOR), "") or "")
                self._paint_title_btn()
            if hasattr(self, "glass_cb"): set_val(self.glass_cb, "setChecked", conf.get(self._get_key(Config.FACECARDS_SHOW_GLASS, Config.DASHBOARD_SHOW_GLASS), True))
            if hasattr(self, "face_int_slider"): set_val(self.face_int_slider, "setValue", conf.get(self._get_key(Config.FACECARDS_GLASS_INTENSITY, Config.DASHBOARD_GLASS_INTENSITY), 5))
            if hasattr(self, "face_border_slider"): set_val(self.face_border_slider, "setValue", conf.get(self._get_key(Config.FACECARDS_GLASS_BORDER, Config.DASHBOARD_GLASS_BORDER), 50))
            if hasattr(self, "hover_effect_cb"): set_val(self.hover_effect_cb, "setChecked", conf.get(self._get_key(Config.FACECARDS_HOVER_EFFECT, Config.DASHBOARD_HOVER_EFFECT), True))
            if hasattr(self, "inline_stats_cb"): set_val(self.inline_stats_cb, "setChecked", conf.get(self._get_key(Config.FACECARDS_INLINE_STATS, Config.DASHBOARD_INLINE_STATS), False))
            if hasattr(self, "tshad_slider"): set_val(self.tshad_slider, "setValue", conf.get(self._get_key(Config.FACECARDS_TITLE_SHADOW_INTENSITY, Config.DASHBOARD_TITLE_SHADOW_INTENSITY), 40))
            if hasattr(self, "sshad_slider"): set_val(self.sshad_slider, "setValue", conf.get(self._get_key(Config.FACECARDS_STAT_SHADOW_INTENSITY, Config.DASHBOARD_STAT_SHADOW_INTENSITY), 60))
        elif self.type == "heatmap":
            if hasattr(self, "scale_slider"): set_val(self.scale_slider, "setValue", conf.get(Config.HEATMAP_SCALE, 100))
            if hasattr(self, "nav_combo"):
                idx = self.nav_combo.findData(conf.get(Config.HEATMAP_NAV_POS, "top_right"))
                if idx >= 0: set_val(self.nav_combo, "setCurrentIndex", idx)
            if hasattr(self, "hide_title_cb"): set_val(self.hide_title_cb, "setChecked", conf.get(Config.HEATMAP_HIDE_TITLE, True))
            if hasattr(self, "hide_labels_cb"): set_val(self.hide_labels_cb, "setChecked", conf.get(Config.HEATMAP_HIDE_LABELS, False))
            if hasattr(self, "show_legend_cb"): set_val(self.show_legend_cb, "setChecked", conf.get(Config.HEATMAP_SHOW_LEGEND, True))
            if hasattr(self, "future_cb"): set_val(self.future_cb, "setChecked", conf.get(Config.HEATMAP_SHOW_FUTURE, True))
            if hasattr(self, "tinted_future_cb"): set_val(self.tinted_future_cb, "setChecked", conf.get(Config.HEATMAP_TINTED_FUTURE, False))
            if hasattr(self, "rounding_slider"): set_val(self.rounding_slider, "setValue", conf.get(Config.HEATMAP_ROUNDING, 20))
            if hasattr(self, "monday_first_cb"): set_val(self.monday_first_cb, "setChecked", conf.get(Config.HEATMAP_MONDAY_FIRST, False))
            
            self.current_color = self._get_effective_heatmap_color()
            self._update_color_button()
            
            if hasattr(self, "opacity_slider"): set_val(self.opacity_slider, "setValue", conf.get(Config.HEATMAP_EMPTY_OPACITY, 15))
            if hasattr(self, "filled_opacity_slider"): set_val(self.filled_opacity_slider, "setValue", conf.get(Config.HEATMAP_FILLED_OPACITY, 100))
            if hasattr(self, "vibrance_slider"): set_val(self.vibrance_slider, "setValue", conf.get(Config.HEATMAP_VIBRANCE, 100))
            if hasattr(self, "intensity_curve_slider"): set_val(self.intensity_curve_slider, "setValue", conf.get(Config.HEATMAP_INTENSITY_CURVE, 100))
            if hasattr(self, "hm_levels_slider"): set_val(self.hm_levels_slider, "setValue", conf.get(Config.HEATMAP_COLOR_LEVELS, 15))
            if hasattr(self, "hm_glass_cb"): set_val(self.hm_glass_cb, "setChecked", conf.get(Config.HEATMAP_SHOW_GLASS, False))
            if hasattr(self, "hm_int_slider"): set_val(self.hm_int_slider, "setValue", conf.get(Config.HEATMAP_GLASS_INTENSITY, 43))
            if hasattr(self, "hm_border_slider"): set_val(self.hm_border_slider, "setValue", conf.get(Config.HEATMAP_GLASS_BORDER, 0))
            if hasattr(self, "show_cont_cb"): set_val(self.show_cont_cb, "setChecked", conf.get(Config.HEATMAP_SHOW_CONTINUOUS_MODE, True))
            if hasattr(self, "show_365_cb"): set_val(self.show_365_cb, "setChecked", conf.get(Config.HEATMAP_SHOW_365_MODE, True))
            if hasattr(self, "show_year_cb"): set_val(self.show_year_cb, "setChecked", conf.get(Config.HEATMAP_SHOW_YEAR_MODE, True))
            if getattr(self, "hm_tooltip_checks", None):
                from ....widgets.chart_utils.tooltip_fields import set_checks
                set_checks(self.hm_tooltip_checks, conf.get(Config.HEATMAP_TOOLTIP_HIDDEN, []))
            if hasattr(self, "click_browser_cb"): set_val(self.click_browser_cb, "setChecked", conf.get(Config.HEATMAP_CLICK_BROWSER, True))
        else:
            if hasattr(self, "glass_cb"): set_val(self.glass_cb, "setChecked", conf.get(Config.PINNED_GLASS, True))
            if hasattr(self, "int_slider"): set_val(self.int_slider, "setValue", conf.get(Config.PINNED_GLASS_INTENSITY, 20))
            if hasattr(self, "border_slider"): set_val(self.border_slider, "setValue", conf.get(Config.PINNED_GLASS_BORDER, 50))
            if hasattr(self, "hover_border_cb"): set_val(self.hover_border_cb, "setChecked", conf.get(Config.PINNED_HOVER_BORDER, True))
            # Activity per-widget toggles always come from widget_def
            if hasattr(self, "avg_cb"): set_val(self.avg_cb, "setChecked", self.widget_def.get("show_average", True))
            if hasattr(self, "cum_cb"): set_val(self.cum_cb, "setChecked", self.widget_def.get("show_cumulative", True))
            if hasattr(self, "chart_opacity_slider"):
                _opc_defaults = {"card_counts": 100, "distribution": 100, "retention": 100}
                _opc_default = _opc_defaults.get(self.type, 100)
                set_val(self.chart_opacity_slider, "setValue", self.widget_def.get("chart_opacity", _opc_default))
            if hasattr(self, "show_legend_cb"):
                set_val(self.show_legend_cb, "setChecked", bool(self.widget_def.get("show_legend", True)))
            if hasattr(self, "legend_mode_combo"):
                set_val(self.legend_mode_combo, "setCurrentIndex", max(0, self.legend_mode_combo.findData(self.widget_def.get("legend_mode", "auto"))))
            for _sl_attr, _sl_key, _sl_conf in (
                ("line_opacity_slider", "line_opacity", Config.CHART_LINE_OPACITY),
                ("bar_gradient_slider", "bar_gradient", Config.CHART_BAR_GRADIENT),
            ):
                if hasattr(self, _sl_attr):
                    set_val(getattr(self, _sl_attr), "setValue", self.widget_def.get(_sl_key, self.addon_config.get(_sl_conf, 100)))
            for _cb_attr, _cb_key, _cb_conf in (
                ("show_grid_cb", "show_grid", Config.CHART_SHOW_GRID),
            ):
                if hasattr(self, _cb_attr):
                    set_val(getattr(self, _cb_attr), "setChecked", bool(self.widget_def.get(_cb_key, self.addon_config.get(_cb_conf, True))))

    def _get_key(self, facecard_key, dashboard_key):
        """Config key for the current context (pinned or Deep Dive)."""
        return dashboard_key if self.is_dashboard_context else facecard_key

    def _is_pinned_separate_theme_mode(self):
        """True when pinned widgets are configured to use a separate theme."""
        if not self.is_pinned_mode:
            return False
        conf = self.global_config if isinstance(self.global_config, dict) else self.addon_config
        return bool(conf.get(Config.PINNED_USE_ACTIVE_THEME, False)) and bool(
            conf.get(Config.PINNED_USE_SEPARATE_THEME, False)
        )

    def _get_pinned_theme_data_color_baseline(self):
        conf = self.global_config if isinstance(self.global_config, dict) else self.addon_config
        preset_key = conf.get(Config.PINNED_THEME_PRESET, ThemePalettes.NATIVE)
        custom_presets = conf.get(Config.THEME_CUSTOM_PRESETS, {})
        entry = custom_presets.get(preset_key, {}) if isinstance(custom_presets, dict) else {}
        if isinstance(entry, dict) and isinstance(entry.get("data_colors"), dict):
            return {**COLOR_DEFAULTS, **entry["data_colors"]}
        return ThemePalettes.get_preset_data_colors(preset_key)

    def _get_heatmap_color_baseline(self):
        if self._is_pinned_separate_theme_mode():
            baseline = self._get_pinned_theme_data_color_baseline()
            return baseline.get(
                Config.HEATMAP_COLOR,
                COLOR_DEFAULTS.get(Config.HEATMAP_COLOR, "#3b82f6"),
            )
        from ..theme.data_color_ops import get_data_color_baseline

        conf = self.global_config if isinstance(self.global_config, dict) else self.addon_config
        return get_data_color_baseline(conf).get(
            Config.HEATMAP_COLOR,
            COLOR_DEFAULTS.get(Config.HEATMAP_COLOR, "#3b82f6"),
        )

    def _get_effective_heatmap_color(self):
        conf = self.global_config if isinstance(self.global_config, dict) else self.addon_config
        if self._is_pinned_separate_theme_mode():
            return get_color(conf, Config.HEATMAP_COLOR, "pinned")
        value = conf.get(Config.HEATMAP_COLOR, "#3b82f6")
        return value if isinstance(value, str) and value.strip() else "#3b82f6"

    def _set_pinned_separate_data_color_override(self, color_key, color_hex):
        conf = self.global_config if isinstance(self.global_config, dict) else self.addon_config
        custom_map = conf.get(Config.PINNED_THEME_CUSTOM_COLORS, {})
        if not isinstance(custom_map, dict):
            custom_map = {}

        baseline_hex = self._get_pinned_theme_data_color_baseline().get(
            color_key,
            COLOR_DEFAULTS.get(color_key, "#888888"),
        )
        if str(color_hex).lower() == str(baseline_hex).lower():
            custom_map.pop(color_key, None)
        else:
            custom_map[color_key] = color_hex

        conf[Config.PINNED_THEME_CUSTOM_COLORS] = custom_map
        has_mode_override = conf.get(Config.PINNED_THEME_CUSTOM_BASE_MODE, None) is not None
        conf[Config.PINNED_THEME_IS_CUSTOM] = bool(custom_map) or has_mode_override

    def apply_live_changes(self):
        """Update the live config object and trigger a style refresh on pinned widgets."""
        conf = self.addon_config
        
        if self.type == "text_label":
            apply_text_label_live_changes(self, conf)
        elif self.type == "stat_card":
            apply_stat_card_live_changes(self, conf)
        elif self.type == "heatmap":
            apply_heatmap_live_changes(self, conf)
        elif self.type == "activity":
            apply_activity_live_changes(self, conf)
        else:
            apply_generic_chart_live_changes(self, conf)

        apply_chart_opacity_live_change(self)

        from ....widgets.pinned.main_menu.manager import MainMenuWidgetManager
        from ....widgets.pinned.widget_factory.factory import WidgetFactory
        
        class DummyCM:
            def __init__(self, c): self.config = c
            def get(self, k, d=None): return self.config.get(k, d)
        
        dm = DummyCM(conf)
        
        target = self.parent()
        if target and isinstance(target, QWidget):
            if self.type != "stat_card":
                WidgetFactory.apply_style(target, config_manager=dm)
            if self.is_pinned_mode and self.type not in ("stat_card", "text_label") and hasattr(self, "label_edit"):
                from aqt.qt import QLabel as _HdrLabel
                _hdr = target.findChild(_HdrLabel, "pinned_header")
                if _hdr is not None:
                    _txt = (self.label_edit.text() or "").strip()
                    _hdr.setText(_txt.upper())
                    _hdr.setVisible(bool(_txt))
            
            # Merge styling config with the widget's own instance definition 
            # to preserve properties like time_span, show_average, etc.
            merged_def = {**self.widget_def, **conf}
            if self.type == "heatmap" and self._is_pinned_separate_theme_mode():
                # Avoid feeding stale global Heatmap_Color into live pinned updates.
                merged_def[Config.HEATMAP_COLOR] = self.current_color
            
            if self.type == "stat_card":
                scale_key = self._get_key(Config.FACECARDS_SCALE, Config.DASHBOARD_SCALE)
                if hasattr(target, "set_scale"):
                    target.set_scale(conf.get(scale_key, 100))
                if self.is_dashboard_context:
                    # When opening settings from a single dashboard row, make sure the
                    # parent row-group container also scales and recomputes height.
                    p = target.parentWidget() if hasattr(target, "parentWidget") else None
                    while p is not None:
                        if hasattr(p, "_rows") and hasattr(p, "set_scale"):
                            p.set_scale(conf.get(scale_key, 100))
                            if hasattr(p, "update_layout"):
                                p.update_layout(p.width())
                            break
                        p = p.parentWidget() if hasattr(p, "parentWidget") else None

                # Make sure immediate style refresh whether parent is the card itself,
                # a stats container, or an intermediate wrapper.
                refreshed_any = False
                if self.is_dashboard_context and hasattr(target, "cards"):
                    current_key = self.widget_def.get("stat_key")
                    for c in getattr(target, "cards", []):
                        if not hasattr(c, "refresh_theme"):
                            continue
                        if self.is_unlinked and getattr(c, "config_key", None) == current_key:
                            c.refresh_theme(conf)
                        else:
                            c.refresh_theme(self.global_config)
                        refreshed_any = True
                elif hasattr(target, "refresh_theme"):
                    target.refresh_theme(conf)
                    refreshed_any = True
                if not self.is_dashboard_context:
                    try:
                        from ....widgets.stats_cards import StatCardWidget
                        for c in target.findChildren(StatCardWidget):
                            c.refresh_theme(conf)
                            refreshed_any = True
                    except Exception:
                        log_swallowed()
                if not refreshed_any and hasattr(target, "cards"):
                    for c in getattr(target, "cards", []):
                        if hasattr(c, "refresh_theme"):
                            c.refresh_theme(conf)
                if self.is_dashboard_context and hasattr(target, "cards"):
                    current_key = self.widget_def.get("stat_key")
                    new_title = (self.label_edit.text() or self._get_default_label()).strip()
                    for c in getattr(target, "cards", []):
                        if getattr(c, "config_key", None) == current_key:
                            try:
                                c.update_val(c.value_lbl.text(), title=new_title, refresh=False)
                            except Exception:
                                log_swallowed()
                    if hasattr(target, "trigger_layout_update"):
                        target.trigger_layout_update()
            elif self.type == "heatmap":
                # Navigation position and "Show at Top" alter structure/order and need
                # an immediate rebuild to reflect in pinned layout.
                if getattr(self, "_heatmap_requires_structure_refresh", False):
                    if MainMenuWidgetManager.instance_exists():
                        MainMenuWidgetManager.instance().refresh(clear_cache=False)
                    self._heatmap_requires_structure_refresh = False
                    return
                from ....widgets.pinned.widget_factory.builders.heatmap import _update_heatmap
                hm = target.findChild(QWidget, "heatmap_widget")
                needs_rebuild = False
                if hm:
                    needs_rebuild = (_update_heatmap(hm, merged_def, merged_def.get("deck_id")) is False)
                elif hasattr(self, "is_grid") and self.is_grid:
                    # Deep dive context: heatmap_widget objectName not set, find by type
                    from ....widgets.charts.heatmap import HeatmapWidget as _HW
                    dd_hm = target.findChild(_HW)
                    if dd_hm:
                        dd_hm.set_monday_first(merged_def.get(Config.HEATMAP_MONDAY_FIRST, False))
                if needs_rebuild:
                    if MainMenuWidgetManager.instance_exists():
                        MainMenuWidgetManager.instance().refresh()
                    return
                if hasattr(self, "show_cont_cb"):
                    from aqt.qt import QPushButton, QLabel as _QLabel
                    cont_v = self.show_cont_cb.isChecked()
                    m365_v = self.show_365_cb.isChecked()
                    year_v = self.show_year_cb.isChecked()
                    btn = target.findChild(QPushButton, "heatmap_mode_cont")
                    if btn: btn.setVisible(cont_v)
                    btn = target.findChild(QPushButton, "heatmap_mode_365")
                    if btn: btn.setVisible(m365_v)
                    btn = target.findChild(QPushButton, "heatmap_mode_year")
                    if btn: btn.setVisible(year_v)
                    s = target.findChild(_QLabel, "heatmap_sep_cont_365")
                    if s: s.setVisible(cont_v and m365_v)
                    s = target.findChild(_QLabel, "heatmap_sep_365_year")
                    if s: s.setVisible(m365_v and year_v)
                    s = target.findChild(_QLabel, "heatmap_sep_cont_year")
                    if s: s.setVisible(cont_v and not m365_v and year_v)
            elif self.type == "activity":
                from ....widgets.pinned.widget_factory.builders.activity import _update_activity
                stack = target.findChild(QWidget, "activity_stack")
                if stack:
                    _update_activity(stack, merged_def, merged_def.get("deck_id"))
            elif self.type == "text_label":
                from aqt.qt import QLabel as _QLabel
                from ....widgets.pinned.widget_factory.builders.text_label import _update_text_label
                label = target.findChild(_QLabel, "pinned_text_label_inner")
                if label:
                    _update_text_label(label, merged_def, merged_def.get("deck_id"), cfg=dm)
            elif self.type == "added":
                from ....widgets.pinned.widget_factory.builders.added import _update_added
                from ....widgets.charts.added_chart import AddedChartWidget
                chart = target.findChild(AddedChartWidget)
                if chart:
                    _update_added(chart, merged_def, merged_def.get("deck_id"))
            elif self.type == "distribution":
                from ....widgets.pinned.widget_factory.builders.distribution import _update_distribution
                from ....widgets.charts.grouped_bar import GroupedBarWidget
                chart = target.findChild(GroupedBarWidget)
                if chart:
                    _update_distribution(chart, merged_def, merged_def.get("deck_id"))
            else:
                if hasattr(target, "refresh_theme"):
                    target.refresh_theme()

            if hasattr(self, "chart_opacity_slider"):
                _opc = self.chart_opacity_slider.value()
                for _child in target.findChildren(QWidget):
                    if hasattr(_child, "set_chart_opacity"):
                        _child.set_chart_opacity(_opc)
            for _sl_attr, _sl_key, _pct_attr in (
                ("line_opacity_slider", "line_opacity", "line_opacity_pct"),
                ("bar_gradient_slider", "bar_gradient", "bar_gradient_pct"),
            ):
                if hasattr(self, _sl_attr):
                    _own = self.widget_def.get(_sl_key)
                    for _child in target.findChildren(QWidget):
                        if hasattr(_child, "set_chart_opacity"):
                            setattr(_child, _pct_attr, None if _own is None else int(_own))
                            _child.update()
            if getattr(self, "tooltip_checks", None):
                for _child in target.findChildren(QWidget):
                    if hasattr(_child, "set_chart_opacity"):
                        _child.tooltip_hidden = list(self.widget_def.get("tooltip_hidden") or [])
            if hasattr(self, "show_legend_cb"):
                for _child in target.findChildren(QWidget):
                    if hasattr(_child, "set_show_legend"):
                        _child.set_show_legend(self.show_legend_cb.isChecked())
            if hasattr(self, "legend_mode_combo"):
                for _child in target.findChildren(QWidget):
                    if hasattr(_child, "set_legend_mode"):
                        _child.set_legend_mode(self.legend_mode_combo.currentData() or "auto")
            for _cb_attr, _cb_key, _flag_attr in (
                ("show_grid_cb", "show_grid", "show_grid_flag"),
            ):
                if hasattr(self, _cb_attr):
                    _own = self.widget_def.get(_cb_key)
                    for _child in target.findChildren(QWidget):
                        if hasattr(_child, "set_chart_opacity"):
                            setattr(_child, _flag_attr, None if _own is None else bool(_own))
                            _child.update()

        if self.is_pinned_mode and not self.is_unlinked:
            if MainMenuWidgetManager.instance_exists():
                MainMenuWidgetManager.instance().update_styles(config_manager=dm)
        
        # Deep Dive mode: global_config is the Deep Dive style dictionary.
        is_deep_dive_mode = bool(self.is_grid) or any(k in self.global_config for k in DEEP_DIVE_STYLE_MARKER_KEYS)
        inplace_only = bool(getattr(self, "_pending_inplace", False))
        self._pending_inplace = False
        if is_deep_dive_mode and not self.is_unlinked and not inplace_only:
             p = self.parent()
             while p:
                 if hasattr(p, "deep_dive_manager"):
                     p.deep_dive_manager._populate_dashboard()
                     break
                 p = p.parentWidget()

    def save_and_close(self):
        self.local_config["use_custom_style"] = self.is_unlinked
        
        if hasattr(self, "label_edit"):
            self.local_config["label"] = self.label_edit.text()
        if self.type == "stat_card" and hasattr(self, "stat_key_combo"):
             self.local_config["stat_key"] = self.stat_key_combo.currentData()
        if self.type == "stat_card" and hasattr(self, "time_unit_combo"):
             self.local_config["time_unit"] = self.time_unit_combo.currentData()
        # Keep per-widget behavior flags synced even when widget_def/local_config
        # are distinct objects (e.g. deep dive contextual settings dialog).
        for _bk in WIDGET_BEHAVIOR_KEYS:
            if _bk in self.widget_def:
                self.local_config[_bk] = self.widget_def[_bk]

        if self.type == "text_label":
            pass

        # Final sync of config values (live updates already applied them).
        try:
            self.apply_live_changes()
        except Exception:
            log_swallowed()

        persist_widget_settings(self)

        if self.type == "text_label":
            pass
        
        self.accept()

    def _setup_text_label_settings(self):
        from aqt.qt import QGroupBox, QVBoxLayout
        from ..widgets.text_label_editor import TextLabelEditor

        group = QGroupBox("Text Widget")
        outer = QVBoxLayout(group)
        outer.setContentsMargins(8, 8, 8, 8)

        self._tl_editor = TextLabelEditor(group, theme_config=self.theme_config or self.addon_config)
        self._tl_editor.set_template(self.widget_def.get("template", ""))
        def _sync_template():
            template = self._tl_editor.get_template()
            self.widget_def["template"] = template
            self.local_config["template"] = template
            self._trigger_live_update()

        self._tl_editor.editor.textChanged.connect(_sync_template)
        outer.addWidget(self._tl_editor)

        self.content_layout.addWidget(group)
        setup_chart_settings(self, include_chart_appearance=False)

    def _setup_facecard_settings(self):
        setup_facecard_settings(self)

    def _setup_heatmap_settings(self):
        setup_heatmap_settings(self)


    def _update_color_button(self):
        update_color_button(self)

    def _select_color(self):
        select_color(self)

    def _reset_color(self):
        reset_color(self)

    def _reset_heatmap(self):
        reset_heatmap(self)

    def _reset_label(self):
        reset_label(self)

    def _get_default_label(self):
        return get_default_label(self)

    def _update_reset_button_visibility(self):
        update_label_reset_button_visibility(self)

    def _setup_chart_settings(self):
        setup_chart_settings(self)

    def _reset_chart_settings(self):
        reset_chart_settings(self)

    def refresh_styles(self):
        """Apply a cleaner, slightly detached style for settings dialogs."""
        theme_conf = self.theme_config if isinstance(self.theme_config, dict) else self.addon_config
        try:
            is_dark = get_theme_effective_is_dark(theme_conf)
        except Exception:
            is_dark = bool(theme_manager.get_night_mode())
        set_qss(self, get_settings_dialog_style(is_dark, theme_conf))
        self._refresh_theme_icons()

    def _get_icon_color(self):
        theme_conf = self.theme_config if isinstance(self.theme_config, dict) else self.addon_config
        try:
            palette = get_theme_palette(theme_conf) or {}
            is_dark = get_theme_effective_is_dark(theme_conf)
            return palette.get("text_secondary", "#a1a1aa" if is_dark else "#71717a")
        except Exception:
            return "#a1a1aa" if bool(theme_manager.get_night_mode()) else "#71717a"

    def _refresh_theme_icons(self):
        icon_col = self._get_icon_color()
        if hasattr(self, "reset_label_btn"):
            self.reset_label_btn.setIcon(get_svg_icon("rotate-ccw", color=icon_col, size=14, context_ref=self))
        if hasattr(self, "reset_color_btn"):
            self.reset_color_btn.setIcon(get_svg_icon("rotate-ccw", color=icon_col, size=14, context_ref=self))
        if hasattr(self, "reset_btn"):
            self.reset_btn.setIcon(get_svg_icon("rotate-ccw", color=icon_col, size=14, context_ref=self))


