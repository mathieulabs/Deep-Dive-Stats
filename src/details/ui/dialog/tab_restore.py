# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .. import Config
from ...logic import log_debug
from ...logic.refresh import queue_ui_callback


def handle_post_tab_change(dialog, index):
    if index < 0:
        return
    if dialog.view_mode == "time":
        dialog._saved_time_tab = index
    else:
        dialog._saved_deck_tab = index

    if not getattr(dialog, "_pending_deep_dive_restore", False):
        return
    if index not in dialog.tab_stats:
        return

    tab_data = dialog.tab_stats[index]
    results = tab_data.get("results", [])
    if not results:
        return

    dialog._pending_deep_dive_restore = False
    conf = dialog.addon_config.config
    identifier = conf.get(Config.DETAILS_DEEP_DIVE_IDENTIFIER)
    title = conf.get(Config.DETAILS_DEEP_DIVE_TITLE, "") or str(identifier or "")
    period_range = conf.get(Config.DETAILS_DEEP_DIVE_PERIOD_RANGE)

    is_valid = False
    if identifier in ["Total", "Collection", "[[TOTAL]]", 0, "0", None] and period_range is None:
        is_valid = True
    elif identifier == "Deleted Cards" or "DELETED CARDS" in str(title).upper():
        is_valid = True
    elif dialog.view_mode == "time":
        for row in results:
            if str(row.get("did")) == str(identifier) or str(row.get("full_name")) == str(identifier):
                is_valid = True
                break
            if row.get("display_name") == identifier:
                is_valid = True
                break
    else:
        for row in results:
            if str(row.get("range_type")) == str(period_range):
                is_valid = True
                break

    if is_valid:
        def _do_restore():
            dialog.deep_dive_manager.open_deep_dive(identifier, title, period_range=period_range)
            if dialog.layout_state == 0 and hasattr(dialog, "layout_toggle_container"):
                dialog.layout_toggle_container.setVisible(True)
            dialog.apply_layout_state(animated=False)

        queue_ui_callback(
            _do_restore,
            delay_ms=0,
            owner=dialog,
            reason="dialog.on_tab_changed.restore_deep_dive",
        )
        return

    log_debug(
        f"[RESTORE] Abandoning restoration: target '{identifier}' (period={period_range}) not found in active tab results.",
        tag="DEEPDIVE",
    )
    dialog.layout_state = 0
    dialog.apply_layout_state(animated=False)
    dialog._save_ui_state()

