# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt import mw
from aqt.qt import QTimer

from .....animations.chart_policy import chart_animation_batch
from ...store.registry import WidgetRegistry
from ...widget_factory.factory import WidgetFactory
from .....logic.logger import log_swallowed


def _collect_partial_refresh_animation_candidates(manager, defs_by_id):
    candidates = []
    seen = set()
    for wid, _definition in list(defs_by_id.items()):
        widget = manager._active_widgets.get(wid)
        if not widget or widget.isHidden():
            continue
        widget_id = id(widget)
        if widget_id in seen:
            continue
        seen.add(widget_id)
        candidates.append(widget)
    return candidates


def on_cache_context_updated(manager):
    if manager._external_refresh_suspensions:
        return
    payload = None
    try:
        from ..imports import GlobalHistoryCache

        cache = GlobalHistoryCache()
        payload = getattr(cache, "_pending_partial_widget_refresh", None)
        cache._pending_partial_widget_refresh = None
    except Exception:
        payload = None

    if isinstance(payload, dict) and payload.get("reason") == "deferred_merge":
        manager._pending_partial_refresh_payload = payload
        if manager._rebuild_in_progress:
            QTimer.singleShot(120, manager._drain_pending_partial_refresh)
            return
        if manager._drain_pending_partial_refresh():
            return

    manager.refresh(clear_cache=False)


def drain_pending_partial_refresh(manager):
    payload = manager._pending_partial_refresh_payload
    if not isinstance(payload, dict):
        return False
    if manager._rebuild_in_progress:
        QTimer.singleShot(120, manager._drain_pending_partial_refresh)
        return True
    manager._pending_partial_refresh_payload = None
    deck_ids = payload.get("deck_ids") or []
    if manager._apply_partial_widget_refresh(deck_ids=deck_ids, reason=payload.get("reason")):
        return True
    manager.refresh(clear_cache=False)
    return True


def apply_partial_widget_refresh(manager, deck_ids, reason):
    if mw.state not in ("deckBrowser", "overview"):
        return False
    if not manager._overlay or not manager._overlay.isVisible():
        return False

    impacted = set(deck_ids or [])
    current_did = manager._current_deck_id
    if mw.state == "overview" and current_did is not None and impacted:
        if current_did not in impacted and None not in impacted:
            return True

    try:
        from ...widget_factory.utils import _get_max_ids

        max_ids = _get_max_ids()
    except Exception:
        max_ids = (0, 0)

    try:
        manager._config_manager = manager._get_config_manager()
        history_cache = manager.__class__._global_history_cache
        defs_by_id = {}
        for definition in WidgetRegistry.get_all():
            wid = definition.get("id")
            if wid is not None:
                defs_by_id[wid] = manager._normalized_widget_def(definition)

        updated_widgets = 0
        deferred_widgets = 0
        animation_candidates = _collect_partial_refresh_animation_candidates(manager, defs_by_id)
        with chart_animation_batch(
            manager._overlay,
            animation_candidates,
            queue_mode=True,
        ):
            for wid, widget in list(manager._active_widgets.items()):
                if not widget or widget.isHidden():
                    continue
                wdef = defs_by_id.get(wid)
                if not wdef:
                    continue
                signature = manager._widget_signature(wdef, current_did, max_ids)
                sync_ok = WidgetFactory.update(
                    widget,
                    wdef,
                    deck_id=current_did,
                    cache=history_cache,
                    fail_if_not_cached=True,
                    cfg=manager._config_manager,
                )
                if sync_ok:
                    updated_widgets += 1
                    manager._widget_update_signatures[wid] = signature
                    if wdef.get("type") == "heatmap" and current_did is None:
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
                    deferred_widgets += 1
                    manager._trigger_async_widget_update(widget, wdef, current_did)

        if updated_widgets or deferred_widgets:
            manager.sync_overlay()
            manager._settle_sync_timer.start(120)

        return True
    except Exception:
        return False




