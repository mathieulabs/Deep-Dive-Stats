# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QSizePolicy, Qt

from ..imports import Config
from ....stats_cards import RowGroupedStatContainer, StatCardWidget
from ...widget_factory.factory import WidgetFactory
from .....logic.logger import log_swallowed


def _stat_box_num(widget_def):
    try:
        return max(0, int(widget_def.get("stat_box", 0) or 0))
    except Exception:
        return 0


def rebuild_stat_cards(
    manager,
    stat_defs,
    normalized_defs,
    deck_id,
    max_ids,
    history_cache,
    non_blocking_update,
    review_return_phase_b_mode,
    review_return_light_mode,
    overview_light_mode,
    pinned_conf,
):
    has_widgets = False
    stats_map = getattr(manager, "_stats_containers", None)
    if not isinstance(stats_map, dict):
        stats_map = {}
        manager._stats_containers = stats_map

    if stat_defs:
        defs_by_box = {}
        cards_by_box = {}
        stat_index = 0

        for wdef in stat_defs:
            wid = wdef["id"]
            wdef_norm = normalized_defs.get(wid, wdef)
            box_num = _stat_box_num(wdef)
            defs_by_box.setdefault(box_num, []).append(wdef)
            widget = None

            if wid in manager._active_widgets:
                widget = manager._active_widgets[wid]
                signature = manager._widget_signature(wdef_norm, deck_id, max_ids)
                if manager._widget_update_signatures.get(wid) == signature:
                    cards_by_box.setdefault(box_num, []).append(widget)
                    has_widgets = True
                    stat_index += 1
                    continue
                if review_return_light_mode and not review_return_phase_b_mode and deck_id is None:
                    cards_by_box.setdefault(box_num, []).append(widget)
                    has_widgets = True
                    stat_index += 1
                    continue
                if review_return_phase_b_mode or review_return_light_mode or overview_light_mode:
                    fast_sync_ok = WidgetFactory.update(
                        widget,
                        wdef_norm,
                        deck_id=deck_id,
                        cache=history_cache,
                        fail_if_not_cached=True,
                        cfg=manager._config_manager,
                    )
                    if fast_sync_ok:
                        manager._widget_update_signatures[wid] = signature
                        cards_by_box.setdefault(box_num, []).append(widget)
                        has_widgets = True
                        stat_index += 1
                        continue

                    delay_ms = 140
                    manager._schedule_deferred_widget_update(
                        widget=widget,
                        widget_def=wdef_norm,
                        deck_id=deck_id,
                        signature=signature,
                        delay_ms=delay_ms,
                        allow_blocking=False,
                    )
                    if review_return_phase_b_mode:
                        pass
                    else:
                        pass
                    cards_by_box.setdefault(box_num, []).append(widget)
                    has_widgets = True
                    stat_index += 1
                    continue
                if not WidgetFactory.update(
                    widget,
                    wdef_norm,
                    deck_id=deck_id,
                    cache=history_cache,
                    fail_if_not_cached=non_blocking_update,
                    cfg=manager._config_manager,
                ):
                    manager._trigger_async_widget_update(widget, wdef_norm, deck_id)
                else:
                    manager._widget_update_signatures[wid] = signature

            if not widget:
                widget = WidgetFactory.create(
                    wdef_norm,
                    deck_id=deck_id,
                    cache=history_cache,
                    parent=manager._overlay,
                    cfg=manager._config_manager,
                )
                if widget:
                    manager._active_widgets[wid] = widget
                    if getattr(widget, "_is_loading", False):
                        manager._trigger_async_widget_update(widget, wdef_norm, deck_id)

            if widget:
                if isinstance(widget, StatCardWidget):
                    widget.set_centered()
                    new_co = int(wdef.get("col_offset", 0))
                    old_co = int(getattr(widget, "_col_offset", 0) or 0)
                    widget._col_offset = new_co
                    if new_co != old_co:
                        pass
                    widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                    try:
                        if widget.receivers(widget.customContextMenuRequested):
                            widget.customContextMenuRequested.disconnect()
                    except Exception:
                        log_swallowed()
                    widget.customContextMenuRequested.connect(
                        lambda pos, w=widget, wid=wid: manager._show_context_menu(w, wid, pos)
                    )
                cards_by_box.setdefault(box_num, []).append(widget)
                has_widgets = True
            stat_index += 1

        used_boxes = sorted(cards_by_box.keys())
        manager._stats_box_order = list(used_boxes)

        for box_num in used_boxes:
            container = stats_map.get(box_num)
            if container is None:
                container = RowGroupedStatContainer(manager._overlay)
                container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                stats_map[box_num] = container

            if container.parent() != manager._overlay:
                container.setParent(manager._overlay)

            container.setProperty("deepdivestats_stat_box", int(box_num))
            from ..runtime.runtime_widget_updates import zoomed_scale

            container.set_scale(zoomed_scale(manager, pinned_conf.get(Config.FACECARDS_SCALE, 100)))
            container.set_compact_mode(True, align="center")
            row_nums = {
                wdef["id"]: int(wdef["row_num"])
                for wdef in defs_by_box.get(box_num, [])
                if wdef.get("row_num")
            }
            container.set_cards(cards_by_box.get(box_num, []), row_nums_by_id=row_nums)
            container.show()

        for box_num, container in stats_map.items():
            if box_num not in used_boxes:
                container.hide()
                container.clear_cards()

        manager._stats_container = stats_map.get(0)
        if manager._stats_container is None and used_boxes:
            manager._stats_container = stats_map.get(used_boxes[0])
    else:
        manager._stats_box_order = []
        for container in stats_map.values():
            container.hide()
            container.clear_cards()
        manager._stats_container = None

    return has_widgets

