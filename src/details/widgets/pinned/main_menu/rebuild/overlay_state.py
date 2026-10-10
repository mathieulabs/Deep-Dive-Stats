# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QVBoxLayout

from ...store.registry import WidgetRegistry
from ..ui.overlay import PinnedOverlay
from ..runtime.overlay_margins import apply_overlay_margins
from ......qss import set_qss
from .....logic.logger import log_swallowed


def _scope_key(manager, deck_id):
    scope_name = "deckBrowser" if bool(getattr(manager, "_is_deck_browser", False)) else "overview"
    return (scope_name, deck_id)


def ensure_overlay_and_rebuild_mode(manager, web, pinned_conf, deck_id):
    if not manager._overlay or manager._overlay.parent() != web:
        target_scope_key = _scope_key(manager, deck_id)
        preserved_by_scope = getattr(manager, "_preserved_widgets_by_scope", None)
        if preserved_by_scope is None:
            preserved_by_scope = {}
            manager._preserved_widgets_by_scope = preserved_by_scope

        current_scope_key = getattr(manager, "_last_render_scope_key", None)
        current_widgets = dict(getattr(manager, "_active_widgets", {}) or {})
        if current_scope_key is not None:
            if current_widgets:
                preserved_by_scope[current_scope_key] = current_widgets
            else:
                preserved_by_scope.pop(current_scope_key, None)

        preserved_widgets = dict(preserved_by_scope.get(target_scope_key, {}) or {})
        if manager._overlay:
            # Detach widgets from the old overlay before deleting it, but keep them
            # parentless until their own scope is restored. Reparenting them to the target
            # web here mixes snapshots across overview and deckBrowser.
            for widget in current_widgets.values():
                widget.hide()
                widget.setParent(None)
            manager._overlay.deleteLater()

        manager._overlay = PinnedOverlay(web)
        manager._overlay.setObjectName("pinned_overlay")
        set_qss(manager._overlay, "background: transparent;")
        manager._overlay.setProperty("deepdivestats_theme_context", "pinned")
        manager._overlay.setProperty("deepdivestats_ignore_forced_dark_theme", True)
        manager._overlay.setProperty("needs_init_geom", True)
        manager._main_layout = QVBoxLayout(manager._overlay)

        manager._stats_container = None
        manager._stats_containers = {}
        manager._stats_box_order = []
        manager._charts_container = None
        manager._chart_boxes = {}
        manager._chart_box_order = []
        manager._texts_container = None
        manager._text_boxes = {}
        manager._text_box_order = []
        manager._masonry_layout = None
        manager._chart_masonry_rows = []
        manager._charts_vbox = None
        manager._text_masonry_rows = []
        manager._texts_vbox = None

        apply_overlay_margins(manager)
        manager._main_layout.setSpacing(4)

        manager._active_widgets = preserved_widgets
        manager._widget_update_signatures = {}
        manager._last_widget_set = tuple(d["id"] for d in WidgetRegistry.get_all())
        manager._last_render_scope_key = target_scope_key
        manager._last_render_deck_id = deck_id
        return True


    current_widget_set = tuple(d["id"] for d in WidgetRegistry.get_all())
    last_widget_set = getattr(manager, "_last_widget_set", None)
    widget_set_changed = last_widget_set != current_widget_set

    should_full_rebuild = bool(widget_set_changed)

    manager._last_widget_set = current_widget_set
    manager._last_render_scope_key = _scope_key(manager, deck_id)
    manager._last_render_deck_id = deck_id
    return should_full_rebuild


def reset_layout_for_full_rebuild(manager):
    while manager._main_layout.count():
        manager._main_layout.takeAt(0)
    stats_map = getattr(manager, "_stats_containers", {}) or {}
    for container in stats_map.values():
        try:
            container.clear_cards()
        except Exception:
            log_swallowed()
    if manager._stats_container:
        manager._stats_container.clear_cards()





