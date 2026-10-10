# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .lifecycle import (
    apply_layout_state,
    close_event,
    on_deep_dive_closed,
    resize_event,
    save_ui_state,
    show_event,
    switch_layout,
    toggle_side_view,
    update_responsive_toolbar,
)
from .settings import open_deck_options, open_settings
from .tab_restore import handle_post_tab_change
