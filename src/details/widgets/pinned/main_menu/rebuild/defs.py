# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ...store.registry import WidgetRegistry
from ..imports import log_debug


def collect_pinned_defs(manager, deck_id):
    pinned_defs_all = WidgetRegistry.get_all()
    pinned_defs = []
    filtered_out = []
    for definition in pinned_defs_all:
        if manager._widget_allowed_in_context(definition, deck_id):
            pinned_defs.append(definition)
        else:
            filtered_out.append(definition)

    if filtered_out:
        log_debug(
            f"rebuild filter: deck_id={deck_id} kept={len(pinned_defs)} dropped={len(filtered_out)} "
            f"dropped_ids={[d.get('id') for d in filtered_out[:8]]}",
            tag="PINNED",
        )

    normalized_defs = {}
    for definition in pinned_defs:
        wid = definition.get("id")
        if wid is not None:
            normalized_defs[wid] = manager._normalized_widget_def(definition)
    return pinned_defs, normalized_defs


def handle_empty_pinned_defs(manager, pinned_defs):
    if pinned_defs:
        return False
    log_debug(
        f"rebuild empty pinned set: hiding overlay and clearing active_widgets={len(manager._active_widgets)}",
        tag="PINNED",
    )
    manager._overlay.hide()
    for wid in list(manager._active_widgets.keys()):
        manager._active_widgets[wid].deleteLater()
        del manager._active_widgets[wid]
        manager._widget_update_signatures.pop(wid, None)
    manager._update_placeholder_height(0)
    return True


def remove_stale_widgets(manager, pinned_defs):
    needed_ids = set(d["id"] for d in pinned_defs)
    to_remove = [wid for wid in manager._active_widgets if wid not in needed_ids]
    for wid in to_remove:
        old_widget = manager._active_widgets[wid]
        manager._remove_widget_from_chart_rows(old_widget)
        old_widget.deleteLater()
        del manager._active_widgets[wid]
        manager._widget_update_signatures.pop(wid, None)


