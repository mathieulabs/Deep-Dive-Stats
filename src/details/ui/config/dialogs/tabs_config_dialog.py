# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QWidget,
    QComboBox,
    QSpinBox,
    Qt,
    QSlider,
    QTabWidget,
)
import copy

from .....config import set_live_config_override

from ... import COLOR_DEFAULTS, Config, ThemePalettes, get_color

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ....dialog import DetailedStatsDialog

from ..theme.ui_helpers import apply_base_mode_button_styles
from ..theme.preset_helpers import (
    get_custom_theme_presets,
    resolve_effective_theme_palette,
)
from ..theme.theme_state import (
    get_current_theme_base_palette,
    get_current_theme_effective_base_mode,
    on_theme_base_mode_changed as on_theme_base_mode_changed_impl,
    set_theme_override_color,
)
from ..theme.runtime_apply import (
    apply_pinned_theme_runtime,
    apply_theme_change,
    refresh_live_data_colors_runtime,
)
from ..theme.pinned_mode_controls import (
    get_pinned_theme_mode_from_config,
    on_pinned_theme_mode_changed as on_pinned_theme_mode_changed_impl,
    update_pinned_theme_controls_state,
)
from ..theme.pinned_theme_state import (
    get_current_pinned_theme_base_palette,
    get_current_pinned_theme_effective_base_mode,
    get_current_pinned_theme_effective_palette,
    on_pinned_theme_base_mode_changed as on_pinned_theme_base_mode_changed_impl,
    set_pinned_theme_override_color,
)
from ..theme.pinned_theme_ui import (
    make_pinned_theme_color_control,
    on_pinned_theme_card_clicked as on_pinned_theme_card_clicked_impl,
    rebuild_pinned_theme_cards,
    refresh_pinned_theme_base_mode_control,
    refresh_pinned_theme_color_controls,
)
from ..theme.theme_ui import (
    make_theme_card_widget,
    make_theme_color_control,
    on_theme_card_clicked as on_theme_card_clicked_impl,
    rebuild_theme_cards,
    refresh_theme_base_mode_control,
    refresh_theme_color_controls,
)
from ..theme.data_colors_ui import (
    make_color_button as make_data_color_button,
    save_global_config as save_global_data_config,
    update_reset_button_visibility as update_data_reset_button_visibility,
)
from .....qss import set_qss
from ..theme.preset_actions import (
    on_delete_theme_preset as on_delete_theme_preset_action,
    on_save_theme_preset as on_save_theme_preset_action,
    on_update_theme_preset as on_update_theme_preset_action,
    update_theme_preset_action_buttons,
)
from ..theme.data_color_ops import (
    apply_data_colors as apply_data_colors_to_ui,
    get_current_data_colors,
    get_data_color_baseline,
    reset_colors_to_default as reset_data_colors_to_default,
)
from ..shared import (
    apply_tab_selection_state,
    apply_standard_dialog_sizing,
    refresh_binning_live,
    clamp_dialog_height,
    find_visible_settings_dialog as find_visible_settings_dialog_shared,
    install_no_wheel_filters,
    load_tabs_list as load_tabs_list_impl,
    refresh_dialog_styles,
    restore_initial_config_snapshot as restore_initial_config_snapshot_impl,
)
from ..shared.dialog_runtime_handlers import (
    on_adaptive_binning_changed as on_adaptive_binning_changed_impl,
    on_animation_scope_changed as on_animation_scope_changed_impl,
    on_chart_animation_threshold_changed as on_chart_animation_threshold_changed_impl,
    on_binning_scale_changed as on_binning_scale_changed_impl,
    on_global_row_height_changed as on_global_row_height_changed_impl,
    on_thousands_separator_changed as on_thousands_separator_changed_impl,
    on_toolbar_button_style_changed as on_toolbar_button_style_changed_impl,
    on_side_view_changed as on_side_view_changed_impl,
    on_stats_precision_changed as on_stats_precision_changed_impl,
    save_and_close as save_and_close_impl,
    update_binning_scale_label as update_binning_scale_label_impl,
)
from ..shared.tab_editor_ops import (
    add_tab as add_tab_impl,
    on_custom_type_changed as on_custom_type_changed_impl,
    on_days_changed as on_days_changed_impl,
    on_enabled_changed as on_enabled_changed_impl,
    on_end_date_changed as on_end_date_changed_impl,
    on_to_today_changed as on_to_today_changed_impl,
    on_range_changed as on_range_changed_impl,
    on_start_date_changed as on_start_date_changed_impl,
    on_title_changed as on_title_changed_impl,
    remove_tab as remove_tab_impl,
    reset_defaults as reset_defaults_impl,
    save_tab_checkbox as save_tab_checkbox_impl,
    save_tab_data as save_tab_data_impl,
    update_visibility as update_visibility_impl,
)
from .general_tab_builder import build_general_tab
from .time_span_tab_builder import build_time_span_tab
from .colors_tab_builder import build_colors_tab


class DetailedStatsConfigDialog(QDialog):
    """Configuration dialog for detailed stats tabs."""
    
    def __init__(self, parent: "DetailedStatsDialog"):
        super().__init__(parent)
        self.parent_dialog = parent
        self.setWindowTitle("Settings")
        self._cancel_restored = False
        
        apply_standard_dialog_sizing(self, min_width=600)
        
        self.tabs_data = parent.get_tabs_config().copy()
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(10)

        self.tabs_widget = QTabWidget(self)
        self.layout.addWidget(self.tabs_widget)
        
        build_general_tab(self)

        build_time_span_tab(self)
        build_colors_tab(self)

        
        self.bottom_area = QWidget(self)
        dialog_btns = QHBoxLayout(self.bottom_area)
        dialog_btns.setContentsMargins(0, 5, 0, 5)
        dialog_btns.addStretch()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.ok_btn = QPushButton("Save")
        self.ok_btn.clicked.connect(self.save_and_close)
        dialog_btns.addWidget(self.cancel_btn)
        dialog_btns.addWidget(self.ok_btn)
        self.layout.addWidget(self.bottom_area)
        
        self.refresh_styles()
        self._install_wheel_filters()
        self.load_tabs_list()
        # Snapshot for true Cancel rollback (live preview can mutate config + write to disk).
        self._initial_tabs_data_snapshot = copy.deepcopy(self.tabs_data)
        self._initial_config_snapshot = copy.deepcopy(self.parent_dialog.addon_config.config)
        # Live readers (chart style, theme, number format) see the edited values before Save.
        set_live_config_override(self.parent_dialog.addon_config.config)
        
        # Compute the final height from size hints (no processEvents, avoids a flash)
        content_h = self.tabs_widget.sizeHint().height()
        footer_h = self.bottom_area.sizeHint().height()
        total_h = content_h + footer_h + 40  # buffer for layout gaps
        
        final_h = clamp_dialog_height(self.max_height, total_h)
        self.resize(720, final_h)

    def _restore_initial_config_snapshot(self):
        restore_initial_config_snapshot_impl(self)

    def reject(self):
        self._restore_initial_config_snapshot()
        super().reject()

    def done(self, result):
        set_live_config_override(None)
        super().done(result)

    def _install_wheel_filters(self):
        """Install event filters to disable wheel on input widgets."""
        install_no_wheel_filters(self, (QComboBox, QSpinBox, QSlider))

    def refresh_styles(self):
        refresh_dialog_styles(self)

    def load_tabs_list(self):
        load_tabs_list_impl(self)

    def on_tab_selected(self, row):
        apply_tab_selection_state(self, row)

    def _get_pinned_theme_mode_from_config(self, conf=None):
        if not isinstance(conf, dict):
            conf = self.parent_dialog.addon_config.config
        return get_pinned_theme_mode_from_config(conf)

    def _on_pinned_theme_mode_changed(self, _index):
        on_pinned_theme_mode_changed_impl(self)

    def _update_pinned_theme_controls_state(self):
        update_pinned_theme_controls_state(self)

    def _refresh_pinned_theme_controls(self):
        self._rebuild_pinned_theme_cards()
        self._refresh_pinned_theme_base_mode_control()
        self._refresh_pinned_theme_color_controls()
        self._update_pinned_theme_controls_state()

    def _get_current_pinned_theme_base_palette(self):
        return get_current_pinned_theme_base_palette(self)

    def _get_current_pinned_theme_effective_base_mode(self):
        return get_current_pinned_theme_effective_base_mode(self)

    def _get_current_pinned_theme_effective_palette(self):
        return get_current_pinned_theme_effective_palette(self)

    def _refresh_pinned_theme_base_mode_control(self):
        refresh_pinned_theme_base_mode_control(self)

    def _update_pinned_theme_base_mode_button_styles(self):
        if not hasattr(self, "pinned_theme_base_mode_buttons"):
            return
        apply_base_mode_button_styles(
            self.pinned_theme_base_mode_buttons, self._get_current_pinned_theme_effective_palette()
        )

    def _refresh_pinned_theme_color_controls(self):
        refresh_pinned_theme_color_controls(self)

    def _set_pinned_theme_override_color(self, color_key, new_hex):
        set_pinned_theme_override_color(self, color_key, new_hex)

    def on_pinned_theme_base_mode_changed(self, selected_mode=None):
        on_pinned_theme_base_mode_changed_impl(self, selected_mode)

    def _make_pinned_theme_color_control(self, color_key):
        return make_pinned_theme_color_control(self, color_key)

    def _rebuild_pinned_theme_cards(self, current_preset=None):
        rebuild_pinned_theme_cards(self, current_preset=current_preset)

    def on_pinned_theme_card_clicked(self, preset_key):
        on_pinned_theme_card_clicked_impl(self, preset_key)

    def _apply_pinned_theme_runtime(self, source="pinned_theme_change"):
        apply_pinned_theme_runtime(self, source)

    def on_thousands_separator_changed(self, state):
        on_thousands_separator_changed_impl(self, state)
    
    def on_toolbar_button_style_changed(self, index):
        on_toolbar_button_style_changed_impl(self)

    def save_global_config(self, key, value):
        save_global_data_config(self, key, value)

    def _is_editing_pinned_data_colors(self):
        if not hasattr(self, "theme_tabs") or not hasattr(self, "pinned_theme_tab"):
            return False
        conf = self.parent_dialog.addon_config.config
        use_active = bool(conf.get(Config.PINNED_USE_ACTIVE_THEME, False))
        use_separate = bool(conf.get(Config.PINNED_USE_SEPARATE_THEME, False))
        if not (use_active and use_separate):
            return False
        pinned_idx = self.theme_tabs.indexOf(self.pinned_theme_tab)
        if pinned_idx < 0:
            return False
        return self.theme_tabs.currentIndex() == pinned_idx

    def _get_pinned_data_color_baseline(self):
        conf = self.parent_dialog.addon_config.config
        preset_key = conf.get(Config.PINNED_THEME_PRESET, ThemePalettes.NATIVE)
        custom_presets = get_custom_theme_presets(conf)
        entry = custom_presets.get(preset_key, {})
        if isinstance(entry, dict) and isinstance(entry.get("data_colors"), dict):
            return {**COLOR_DEFAULTS, **entry["data_colors"]}
        return ThemePalettes.get_preset_data_colors(preset_key)

    def _set_data_color_value(self, key, value):
        conf = self.parent_dialog.addon_config.config
        if not self._is_editing_pinned_data_colors():
            conf[key] = value
            return

        custom_map = conf.get(Config.PINNED_THEME_CUSTOM_COLORS, {})
        if not isinstance(custom_map, dict):
            custom_map = {}

        baseline = self._get_pinned_data_color_baseline()
        base_hex = baseline.get(key, COLOR_DEFAULTS.get(key, "#888888"))
        if str(value).lower() == str(base_hex).lower():
            custom_map.pop(key, None)
        else:
            custom_map[key] = value

        conf[Config.PINNED_THEME_CUSTOM_COLORS] = custom_map
        has_mode_override = conf.get(Config.PINNED_THEME_CUSTOM_BASE_MODE, None) is not None
        conf[Config.PINNED_THEME_IS_CUSTOM] = bool(custom_map) or has_mode_override

    def _get_data_color_current(self, key):
        conf = self.parent_dialog.addon_config.config
        baseline_hex = self._get_data_color_baseline().get(key, COLOR_DEFAULTS.get(key, "#888888"))
        if self._is_editing_pinned_data_colors():
            return get_color(conf, key, "pinned")
        value = conf.get(key, baseline_hex)
        return value if isinstance(value, str) and value.strip() else baseline_hex

    def _resolve_data_color_storage_key(self, storage_key):
        for key in COLOR_DEFAULTS.keys():
            if storage_key == key or storage_key.startswith(f"{key}_"):
                return key
        return None

    def _refresh_data_color_controls(self):
        if not hasattr(self, "_color_buttons"):
            return
        if hasattr(self, "data_color_context_hint"):
            if self._is_editing_pinned_data_colors():
                self.data_color_context_hint.setText(
                    "Data colors currently target Pinned (separate pinned theme mode)."
                )
            else:
                self.data_color_context_hint.setText(
                    "Data colors currently target Details (global details theme)."
                )
        for storage_key, btn in self._color_buttons.items():
            key = self._resolve_data_color_storage_key(storage_key)
            if not key:
                continue
            hex_val = self._get_data_color_current(key)
            set_qss(btn, 
                f"background-color: {hex_val}; border: 1px solid rgba(128,128,128,0.45); border-radius: 4px;"
            )
        for storage_key, lbl in self._hex_labels.items():
            key = self._resolve_data_color_storage_key(storage_key)
            if not key:
                continue
            lbl.setText(str(self._get_data_color_current(key)).upper())
        for storage_key, btn_reset in self._reset_buttons.items():
            key = self._resolve_data_color_storage_key(storage_key)
            if not key:
                continue
            self._update_reset_button_visibility(key, btn_reset)

    def _make_color_button(self, config_key, unique_suffix=""):
        """Create a colored swatch button with hex label and reset arrow."""
        return make_data_color_button(self, config_key, unique_suffix)

    def _update_reset_button_visibility(self, config_key, btn_reset):
        """Show reset button only if current color differs from active preset baseline."""
        update_data_reset_button_visibility(self, config_key, btn_reset)

    def _get_data_color_baseline(self):
        """Return expected data colors for currently selected preset."""
        conf = self.parent_dialog.addon_config.config
        if self._is_editing_pinned_data_colors():
            return self._get_pinned_data_color_baseline()
        return get_data_color_baseline(conf)

    def _reset_colors_to_default(self):
        """Reset all color config keys to active preset baseline and update UI."""
        cfg = self.parent_dialog.addon_config.config
        reset_data_colors_to_default(
            conf=cfg,
            baseline=self._get_data_color_baseline(),
            save_global_config=self.save_global_config,
            color_buttons=self._color_buttons,
            hex_labels=self._hex_labels,
            reset_buttons=self._reset_buttons,
            update_reset_button_visibility=self._update_reset_button_visibility,
            write_config=self.parent_dialog.addon_config.write_config,
        )
        self._refresh_data_color_controls()


    def _get_current_data_colors(self):
        """Return current stat + card type colors as a dict {config_key: hex}."""
        cfg = self.parent_dialog.addon_config.config
        return get_current_data_colors(cfg)

    def _apply_data_colors(self, data_colors):
        """Apply a data_colors dict to config and refresh color button UI."""
        cfg = self.parent_dialog.addon_config.config
        apply_data_colors_to_ui(
            conf=cfg,
            data_colors=data_colors,
            color_buttons=self._color_buttons,
            hex_labels=self._hex_labels,
            reset_buttons=self._reset_buttons,
            update_reset_button_visibility=self._update_reset_button_visibility,
        )
        self._refresh_data_color_controls()

    def _update_theme_preset_action_buttons(self):
        update_theme_preset_action_buttons(self)

    def _get_current_theme_base_palette(self):
        return get_current_theme_base_palette(self)

    def _get_current_theme_effective_base_mode(self):
        return get_current_theme_effective_base_mode(self)

    def _refresh_theme_base_mode_control(self):
        refresh_theme_base_mode_control(self)

    def _update_theme_base_mode_button_styles(self):
        if not hasattr(self, "theme_base_mode_buttons"):
            return
        apply_base_mode_button_styles(
            self.theme_base_mode_buttons, self._get_current_theme_effective_palette()
        )

    def _get_current_theme_effective_palette(self):
        conf = self.parent_dialog.addon_config.config
        base_palette = self._get_current_theme_base_palette()
        return resolve_effective_theme_palette(base_palette, conf)

    def _refresh_theme_color_controls(self):
        refresh_theme_color_controls(self)

    def _apply_theme_change(self):
        apply_theme_change(self)

    def _refresh_live_data_colors(self, source=None, emit_theme_runtime=True):
        refresh_live_data_colors_runtime(self, source=source, emit_theme_runtime=emit_theme_runtime)

    def _set_theme_override_color(self, color_key, new_hex):
        set_theme_override_color(self, color_key, new_hex)

    def on_theme_base_mode_changed(self, selected_mode=None):
        on_theme_base_mode_changed_impl(self, selected_mode)

    def _make_theme_color_control(self, color_key):
        return make_theme_color_control(self, color_key)

    def _rebuild_theme_cards(self, current_preset=None):
        rebuild_theme_cards(self, current_preset=current_preset)

    def _make_theme_card(self, preset_key, preset_name, current_preset, on_click, parent_widget=None):
        """Create a clickable theme card showing name + color swatches."""
        return make_theme_card_widget(
            self,
            preset_key=preset_key,
            preset_name=preset_name,
            current_preset=current_preset,
            on_click=on_click,
            parent_widget=parent_widget,
        )

    def on_theme_card_clicked(self, preset_key):
        """Select a theme preset and clear temporary unsaved edits."""
        on_theme_card_clicked_impl(self, preset_key)

    def on_update_theme_preset(self):
        """Overwrite the currently selected custom preset with current effective colors."""
        on_update_theme_preset_action(self)

    def on_save_theme_preset(self):
        """Persist current effective theme colors as a distinct selectable preset."""
        on_save_theme_preset_action(self)

    def on_delete_theme_preset(self):
        """Delete the currently selected custom theme preset."""
        on_delete_theme_preset_action(self)

    def save_tab_data(self, key, value):
        save_tab_data_impl(self, key, value)

    def _save_tab_checkbox(self, key, state):
        save_tab_checkbox_impl(self, key, state)

    def on_custom_type_changed(self, index):
        on_custom_type_changed_impl(self)

    def on_start_date_changed(self, date):
        on_start_date_changed_impl(self, date)

    def on_end_date_changed(self, date):
        on_end_date_changed_impl(self, date)

    def on_to_today_changed(self, state):
        on_to_today_changed_impl(self, state)

    def update_visibility(self):
        update_visibility_impl(self)

    def on_enabled_changed(self, state):
        on_enabled_changed_impl(self, state)

    def on_title_changed(self, text):
        on_title_changed_impl(self, text)

    def on_range_changed(self, index):
        on_range_changed_impl(self)

    def on_days_changed(self, value):
        on_days_changed_impl(self, value)

    def add_tab(self):
        add_tab_impl(self)

    def remove_tab(self):
        remove_tab_impl(self)

    def reset_defaults(self):
        reset_defaults_impl(self)

    def on_full_name_changed(self, state):
        self.parent_dialog.addon_config.config[Config.SHOW_FULL_DECK_NAME] = (state == Qt.CheckState.Checked.value)


    def on_adaptive_binning_changed(self, state):
        on_adaptive_binning_changed_impl(self, state)

    def _update_binning_scale_label(self, scale):
        update_binning_scale_label_impl(self, scale)

    def on_binning_scale_changed(self, value):
        on_binning_scale_changed_impl(self, value)

    def _refresh_binning_live(self):
        refresh_binning_live(self)

    def on_side_view_changed(self, state):
        on_side_view_changed_impl(self, state)

    def on_animation_scope_changed(self, _index):
        on_animation_scope_changed_impl(self)

    def on_chart_animation_threshold_changed(self, value):
        on_chart_animation_threshold_changed_impl(self, value)

    def on_global_row_height_changed(self, value):
        on_global_row_height_changed_impl(self, value)

    def on_stats_precision_changed(self, value):
        on_stats_precision_changed_impl(self, value)

    def save_and_close(self):
        save_and_close_impl(self)

def find_visible_settings_dialog():
    return find_visible_settings_dialog_shared(DetailedStatsConfigDialog)





