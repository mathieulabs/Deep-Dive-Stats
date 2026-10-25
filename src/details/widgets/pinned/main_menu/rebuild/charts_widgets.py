# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QTimer, Qt

from .....animations.chart_policy import chart_animation_batch
from ..constants import CHART_FADE_IN_MS, CHART_REFLOW_DISABLE_DELAY_MS, IMMEDIATE_TIMER_MS
from ...widget_factory.factory import WidgetFactory
from .....logic.logger import log_swallowed


def _clear_no_move_flag(widget):
    try:
        widget.setProperty("deepdivestats_no_reflow_move_once", False)
    except RuntimeError:
        pass  # widget already deleted


def _chart_box_num(widget_def):
    try:
        return max(0, int(widget_def.get("chart_box", 0) or 0))
    except Exception:
        return 0


def _text_box_num(widget_def):
    try:
        return max(0, int(widget_def.get("text_box", widget_def.get("chart_box", 0)) or 0))
    except Exception:
        return 0


def _place_in_registry_order(manager, masonry, widget, wid, registry_order):
    my_idx = registry_order.get(wid)
    if my_idx is None:
        return
    widget_ids = {id(w): w_id for w_id, w in manager._active_widgets.items() if w is not None}
    src = None
    target = None
    for i in range(masonry.count()):
        item = masonry.itemAt(i)
        w = item.widget() if item is not None else None
        if w is widget:
            src = i
            continue
        other_idx = registry_order.get(widget_ids.get(id(w)))
        if target is None and other_idx is not None and other_idx > my_idx:
            target = i
    if src is None or target is None:
        return
    if target > src:
        target -= 1
    masonry.move_item(src, target)


def _collect_sync_update_candidates(
    manager,
    other_defs,
    normalized_defs,
    deck_id,
    max_ids,
    review_return_light_mode,
    review_return_phase_b_mode,
    overview_light_mode,
    overview_sync_budget,
    widget_index,
):
    candidates = []
    scan_widget_index = int(widget_index or 0)
    for wdef in other_defs:
        wid = wdef["id"]
        widget = manager._active_widgets.get(wid)
        if widget:
            wdef_norm = normalized_defs.get(wid, wdef)
            signature = manager._widget_signature(wdef_norm, deck_id, max_ids)
            if manager._widget_update_signatures.get(wid) != signature:
                wtype = wdef.get("type")
                force_defer_heatmap = bool(review_return_light_mode and wtype == "heatmap")
                force_defer_phase_b = bool(review_return_phase_b_mode)
                # In phase A, defer all charts so they animate once with fresh phase-B data.
                force_defer_review_return_phase_a = bool(review_return_light_mode and not review_return_phase_b_mode)
                should_defer = force_defer_phase_b or force_defer_heatmap or force_defer_review_return_phase_a or (scan_widget_index >= overview_sync_budget)
                if not should_defer:
                    candidates.append(widget)
            scan_widget_index += 1
    return candidates


def rebuild_charts_widgets(
    manager,
    other_defs,
    normalized_defs,
    deck_id,
    max_ids,
    history_cache,
    non_blocking_update,
    review_return_light_mode,
    review_return_phase_b_mode,
    overview_light_mode,
    overview_sync_budget,
    pinned_conf,
    charts_exist,
    widget_index,
    has_widgets,
    should_full_rebuild,
):
    registry_order = {wid: i for i, wid in enumerate(normalized_defs)}
    used_chart_boxes = []
    used_chart_box_set = set()
    used_text_boxes = []
    used_text_box_set = set()
    if should_full_rebuild:
        for box_map in (getattr(manager, "_chart_boxes", {}), getattr(manager, "_text_boxes", {})):
            for box_id, box in sorted(box_map.items(), key=lambda kv: kv[0]):
                rows = box.get("rows", [])
                for row_w, row_ml in rows:
                    row_ml.clear_items()
                    row_w.hide()
                vbox = box.get("vbox")
                while vbox and vbox.count():
                    vbox.takeAt(0)
                box["rows"] = []
                box["masonry"] = None
                if box_id != 0:
                    container = box.get("container")
                    if container is not None:
                        container.hide()
    sync_update_candidates = _collect_sync_update_candidates(
        manager,
        other_defs=other_defs,
        normalized_defs=normalized_defs,
        deck_id=deck_id,
        max_ids=max_ids,
        review_return_light_mode=review_return_light_mode,
        review_return_phase_b_mode=review_return_phase_b_mode,
        overview_light_mode=overview_light_mode,
        overview_sync_budget=overview_sync_budget,
        widget_index=widget_index,
    )

    with chart_animation_batch(
        manager._overlay,
        sync_update_candidates,
        force_repaint_candidates=(len(sync_update_candidates) <= 1),
        queue_mode=True,
    ):
        for wdef in other_defs:
            wid = wdef["id"]
            wdef_norm = normalized_defs.get(wid, wdef)
            wtype = wdef.get("type")
            widget = manager._active_widgets.get(wid)
            created_now = False

            if not widget:
                widget = WidgetFactory.create(
                    wdef_norm,
                    deck_id=deck_id,
                    cache=history_cache,
                    cfg=manager._config_manager,
                )
                if widget:
                    manager._active_widgets[wid] = widget
                    created_now = True
                    if wtype in ("activity", "retention"):
                        from ...context_access import get_pinned_context

                        span_for_ctx = manager._normalize_time_span(wdef_norm.get("time_span"), wtype)
                        custom_days = int(wdef_norm.get("custom_days", 7) or 7)
                        ctx = get_pinned_context(
                            deck_id,
                            span_for_ctx,
                            cfg=manager._config_manager,
                            custom_days=custom_days,
                            allow_slow_ops=False,
                        )
                        if wtype == "activity":
                            ctx_has_data = bool((ctx or {}).get("activity_data"))
                        else:
                            ctx_has_data = bool((ctx or {}).get("retention_data"))
                        loading_flag = bool(getattr(widget, "_is_loading", False))
                        should_trigger_async = loading_flag or (not ctx_has_data)
                        if should_trigger_async:
                            manager._trigger_async_widget_update(widget, wdef_norm, deck_id)
                    elif getattr(widget, "_is_loading", False):
                        manager._trigger_async_widget_update(widget, wdef_norm, deck_id)

            if widget:
                signature = manager._widget_signature(wdef_norm, deck_id, max_ids)
                if created_now:
                    manager._widget_update_signatures[wid] = signature
                elif manager._widget_update_signatures.get(wid) != signature:
                    force_defer_heatmap = bool(review_return_light_mode and wtype == "heatmap")
                    force_defer_phase_b = bool(review_return_phase_b_mode)
                    # In phase A, skip deferred updates entirely, signatures stay unset so
                    # phase B will run a single animation with fresh data.
                    force_defer_review_return_phase_a = bool(review_return_light_mode and not review_return_phase_b_mode)
                    should_defer = force_defer_phase_b or force_defer_heatmap or force_defer_review_return_phase_a or (widget_index >= overview_sync_budget)
                    if should_defer:
                        if force_defer_review_return_phase_a:
                            # Phase A: leave signature unset, phase B will handle it.
                            pass
                        else:
                            if force_defer_heatmap:
                                delay_ms = (260 + (widget_index * 80)) if review_return_phase_b_mode else (180 + (widget_index * 60))
                            elif review_return_light_mode:
                                if review_return_phase_b_mode:
                                    delay_ms = 220 + ((widget_index - overview_sync_budget + 1) * 80)
                                else:
                                    delay_ms = 120 + ((widget_index - overview_sync_budget + 1) * 60)
                            else:
                                delay_ms = (widget_index - overview_sync_budget + 1) * 60
                            manager._schedule_deferred_widget_update(
                                widget=widget,
                                widget_def=wdef_norm,
                                deck_id=deck_id,
                                signature=signature,
                                delay_ms=delay_ms,
                                allow_blocking=force_defer_heatmap,
                            )
                    else:
                        sync_ok = WidgetFactory.update(
                            widget,
                            wdef_norm,
                            deck_id=deck_id,
                            cache=history_cache,
                            fail_if_not_cached=non_blocking_update,
                            cfg=manager._config_manager,
                        )
                        if sync_ok:
                            manager._widget_update_signatures[wid] = signature
                            if wtype == "heatmap" and deck_id is None:
                                try:
                                    manager._clear_browser_heatmap_snapshot_overlay()
                                except Exception:
                                    log_swallowed()
                            if getattr(widget, "_is_loading", False):
                                widget._is_loading = False
                                try:
                                    manager._fade_in_widget(widget)
                                except Exception:
                                    log_swallowed()
                        else:
                            if widget_index < 4:
                                manager._trigger_async_widget_update(widget, wdef_norm, deck_id)
                            else:
                                delay_ms = (widget_index - 3) * 50
                                QTimer.singleShot(
                                    delay_ms,
                                    lambda w=widget, wd=wdef_norm, d=deck_id: manager._trigger_async_widget_update(w, wd, d),
                                )
                widget_index += 1

            if widget:
                has_widgets = True
                box_kind = "text" if wtype == "text_label" else "chart"
                if box_kind == "chart":
                    charts_exist = True
                row_num = int(wdef.get("row_num", 0))
                chart_box = _chart_box_num(wdef)
                target_box = _text_box_num(wdef) if box_kind == "text" else chart_box
                if box_kind == "text":
                    if target_box not in used_text_box_set:
                        used_text_box_set.add(target_box)
                        used_text_boxes.append(target_box)
                else:
                    if target_box not in used_chart_box_set:
                        used_chart_box_set.add(target_box)
                        used_chart_boxes.append(target_box)
                target_masonry = manager._get_or_create_chart_masonry_row(
                    row_num,
                    chart_box=target_box,
                    box_kind=box_kind,
                )
                # A card shown fullscreen is still "in" its row (a placeholder holds its slot).
                already_in = bool(getattr(widget, "_fullscreen_active", False)) or any(
                    item.widget() == widget
                    for _box in (
                        list(getattr(manager, "_chart_boxes", {}).values())
                        + list(getattr(manager, "_text_boxes", {}).values())
                    )
                    for _, ml_check in _box.get("rows", [])
                    for item in getattr(ml_check, "itemList", [])
                )
                if not already_in:
                    widget.setProperty("deepdivestats_no_reflow_move_once", True)
                    # The flag only skips the move animation of the first reflow. Clear it
                    # after that window, or the first drag reorder would jump without animation.
                    QTimer.singleShot(
                        CHART_REFLOW_DISABLE_DELAY_MS + 200,
                        lambda w=widget: _clear_no_move_flag(w),
                    )
                    target_masonry.addWidget(widget)
                    # A widget (re)created now, e.g. shown again after a deck that
                    # hides it, goes back to its saved spot in the row, not the end.
                    _place_in_registry_order(manager, target_masonry, widget, wid, registry_order)
                    QTimer.singleShot(
                        IMMEDIATE_TIMER_MS,
                        lambda w=widget: manager._fade_in_widget(w, duration=CHART_FADE_IN_MS),
                    )
                elif widget.isHidden():
                    widget.show()

                try:
                    from ...zoom_link import attach as _attach_zoom_link

                    _attach_zoom_link(manager, widget)
                except Exception:
                    log_swallowed()

                widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                try:
                    if widget.receivers(widget.customContextMenuRequested):
                        widget.customContextMenuRequested.disconnect()
                except Exception:
                    log_swallowed()
                widget.customContextMenuRequested.connect(
                    lambda pos, w=widget, wid=wid: manager._show_context_menu(w, wid, pos)
                )

    for box_map in (getattr(manager, "_chart_boxes", {}), getattr(manager, "_text_boxes", {})):
        for box in box_map.values():
            for row_w, row_ml in box.get("rows", []):
                is_empty = row_ml.count() == 0
                row_w.setMinimumHeight(0 if is_empty else 0)
                row_w.setVisible(not is_empty)

    if charts_exist:
        manager._chart_box_order = list(used_chart_boxes)
        for box_id, box in sorted(getattr(manager, "_chart_boxes", {}).items(), key=lambda kv: kv[0]):
            container = box.get("container")
            if container is None:
                continue
            if box_id in used_chart_box_set:
                if container.isHidden():
                    container.show()
            else:
                container.hide()

        default_box = getattr(manager, "_chart_boxes", {}).get(0)
        if default_box:
            manager._charts_container = default_box.get("container")
            manager._charts_vbox = default_box.get("vbox")
            manager._chart_masonry_rows = default_box.get("rows", [])
            manager._masonry_layout = default_box.get("masonry")
    else:
        manager._chart_box_order = []
        for box in getattr(manager, "_chart_boxes", {}).values():
            container = box.get("container")
            if container is not None:
                container.hide()

    manager._text_box_order = list(used_text_boxes)
    for box_id, box in sorted(getattr(manager, "_text_boxes", {}).items(), key=lambda kv: kv[0]):
        container = box.get("container")
        if container is None:
            continue
        if box_id in used_text_box_set:
            if container.isHidden():
                container.show()
        else:
            container.hide()

    default_text_box = getattr(manager, "_text_boxes", {}).get(0)
    if default_text_box:
        manager._texts_container = default_text_box.get("container")
        manager._texts_vbox = default_text_box.get("vbox")
        manager._text_masonry_rows = default_text_box.get("rows", [])
    else:
        manager._texts_container = None
        manager._texts_vbox = None
        manager._text_masonry_rows = []

    return has_widgets, charts_exist, widget_index
