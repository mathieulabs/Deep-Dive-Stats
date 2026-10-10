# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .dialog_sizing import apply_standard_dialog_sizing, clamp_dialog_height, clamp_dialog_width
from .range_options import RANGE_OPTIONS
from .tab_mutations import (
    append_new_tab,
    format_tab_list_title,
    remove_tab,
    set_tab_enabled,
    set_tab_field,
    set_tab_title,
)
from .tab_selection_state import apply_tab_selection_state
from .binning_live_refresh import refresh_binning_live
from .dialog_lifecycle import (
    find_visible_settings_dialog,
    load_tabs_list,
    refresh_dialog_styles,
    restore_initial_config_snapshot,
)
from .wheel_filter import NoWheelFilter, install_no_wheel_filters, no_wheel_filter

__all__ = [
    "NoWheelFilter",
    "no_wheel_filter",
    "install_no_wheel_filters",
    "apply_standard_dialog_sizing",
    "clamp_dialog_height",
    "clamp_dialog_width",
    "RANGE_OPTIONS",
    "set_tab_field",
    "set_tab_enabled",
    "set_tab_title",
    "append_new_tab",
    "remove_tab",
    "format_tab_list_title",
    "apply_tab_selection_state",
    "refresh_binning_live",
    "restore_initial_config_snapshot",
    "refresh_dialog_styles",
    "load_tabs_list",
    "find_visible_settings_dialog",
]

