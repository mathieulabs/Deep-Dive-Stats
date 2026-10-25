# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import time
from typing import Any, ClassVar

from .imports import GlobalHistoryCache, QObject, QTimer, ConfigManager, get_theme_manager, mw
from .state import OverlayState, RuntimeState
from .constants import (
    CHART_FADE_IN_MS,
    CHART_FADE_OUT_MS,
    POLL_INTERVAL_MS,
)
from .ui.context_menu import PinnedContextMenu
from .ui.widget_defs import (
    widget_allowed_in_context as widget_allowed_in_context_impl,
    normalize_time_span as normalize_time_span_impl,
    normalized_widget_def as normalized_widget_def_impl,
    widget_signature as widget_signature_impl,
)
from .runtime.overlay_sync import (
    schedule_overlay_sync as schedule_overlay_sync_impl,
    run_scheduled_overlay_sync as run_scheduled_overlay_sync_impl,
    update_overlay_geom as update_overlay_geom_impl,
    current_resize_signature as current_resize_signature_impl,
    resize_overlay as resize_overlay_impl,
    update_placeholder_height as update_placeholder_height_impl,
    sync_overlay as sync_overlay_impl,
    do_sync_overlay as do_sync_overlay_impl,
)
from .runtime.hook_events import (
    register_hooks as register_hooks_impl,
    on_sync_did_finish as on_sync_did_finish_impl,
    on_operation_did_execute as on_operation_did_execute_impl,
    run_operation_refresh as run_operation_refresh_impl,
    on_profile_did_open as on_profile_did_open_impl,
    on_internal_theme_changed as on_internal_theme_changed_impl,
    on_theme_change as on_theme_change_impl,
)
from .ui.context_actions import (
    show_context_menu as show_context_menu_impl,
    open_details_dialog as open_details_dialog_impl,
    open_time_span_settings as open_time_span_settings_impl,
    open_widget_settings as open_widget_settings_impl,
    update_span as update_span_impl,
    update_span_bulk as update_span_bulk_impl,
    update_setting as update_setting_impl,
    toggle_global_bottom_stats as toggle_global_bottom_stats_impl,
    toggle_global_show_stats as toggle_global_show_stats_impl,
    unpin as unpin_impl,
    reset_widget_size as reset_widget_size_impl,
)
from .rebuild.control import (
    on_rebuild_timer_timeout as on_rebuild_timer_timeout_impl,
    on_refresh_timer_timeout as on_refresh_timer_timeout_impl,
    schedule_rebuild as schedule_rebuild_impl,
    rebuild_overlay as rebuild_overlay_impl,
)
from .rebuild.inner import rebuild_overlay_inner as rebuild_overlay_inner_impl
from .runtime.refresh_control import (
    refresh as refresh_impl,
    set_external_refresh_suspended as set_external_refresh_suspended_impl,
)
from .runtime.partial_refresh import (
    on_cache_context_updated as on_cache_context_updated_impl,
    drain_pending_partial_refresh as drain_pending_partial_refresh_impl,
    apply_partial_widget_refresh as apply_partial_widget_refresh_impl,
)
from .runtime.style_update import update_styles as update_styles_impl
from .runtime.runtime_widget_updates import (
    schedule_deferred_widget_update as schedule_deferred_widget_update_impl,
    get_zoom_factor as get_zoom_factor_impl,
    apply_zoom_scale_to_widgets as apply_zoom_scale_to_widgets_impl,
    trigger_async_widget_update as trigger_async_widget_update_impl,
)
from .ui.chart_row_ops import (
    get_or_create_chart_masonry_row as get_or_create_chart_masonry_row_impl,
    set_chart_rows_animate_moves as set_chart_rows_animate_moves_impl,
    run_chart_reflow_animation_pass as run_chart_reflow_animation_pass_impl,
    schedule_chart_reflow_animation as schedule_chart_reflow_animation_impl,
    mark_skip_next_show_anim as mark_skip_next_show_anim_impl,
    fade_in_widget as fade_in_widget_impl,
    fade_out_widget as fade_out_widget_impl,
    remove_widget_from_chart_rows as remove_widget_from_chart_rows_impl,
    prune_chart_rows as prune_chart_rows_impl,
)
from .runtime.web_bridge import (
    on_webview_did_inject_style as on_webview_did_inject_style_impl,
    get_placeholder_js as get_placeholder_js_impl,
    inject_placeholder as inject_placeholder_impl,
    on_js_message as on_js_message_impl,
    event_filter as event_filter_impl,
)
from .runtime.navigation_flow import (
    on_state_did_change as on_state_did_change_impl,
    on_deck_browser_will_render as on_deck_browser_will_render_impl,
    on_overview_will_render as on_overview_will_render_impl,
    on_reviewer_did_init as on_reviewer_did_init_impl,
    on_reviewer_will_end as on_reviewer_will_end_impl,
)
from .ui.chart_drag_ops import (
    handle_chart_move as handle_chart_move_impl,
    finalize_chart_reorder as finalize_chart_reorder_impl,
)
from ....logic.logger import log_swallowed

class MainMenuWidgetManager(QObject):
    _instance: ClassVar["MainMenuWidgetManager | None"] = None
    _global_history_cache: ClassVar[dict[Any, Any]] = {}  # Shared across rebuilds
    _global_cache_instance: ClassVar[Any] = None  # Real GlobalHistoryCache singleton instance
    _last_max_rev_id: ClassVar[int | None] = None

    @classmethod
    def instance(cls) -> "MainMenuWidgetManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def instance_exists(cls) -> bool:
        return cls._instance is not None

    def __init__(self) -> None:
        super().__init__()
        self._runtime_state = RuntimeState()
        self._overlay_state = OverlayState()
        self._theme_manager = get_theme_manager()
        self._theme_manager.subscribe(self._on_internal_theme_changed)
        self._overlay = None
        self._stats_container = None
        self._stats_containers = {}
        self._stats_box_order = []
        self._charts_container = None
        self._chart_boxes = {}
        self._chart_box_order = []
        self._texts_container = None
        self._text_boxes = {}
        self._text_box_order = []
        self._masonry_layout = None
        self._chart_masonry_rows = []   # list of (QWidget, MasonryLayout) per row group
        self._charts_vbox = None        # QVBoxLayout inside _charts_container
        self._text_masonry_rows = []
        self._texts_vbox = None
        self._active_widgets = {} # widget_id -> widget instance
        self._preserved_widgets_by_scope = {}
        self._last_render_scope_key = None
        self._heatmap_snapshot_label = None
        self._current_deck_id = self._runtime_state.current_deck_id
        self._is_deck_browser = self._runtime_state.is_deck_browser
        self._main_layout = None
        self._context_menu = PinnedContextMenu(self)
        self._last_geom = self._overlay_state.last_geom
        self._rebuild_in_progress = self._runtime_state.rebuild_in_progress
        self._scheduled_deck_id = self._runtime_state.scheduled_deck_id
        self._rebuild_timer = QTimer()
        self._rebuild_timer.setSingleShot(True)
        self._rebuild_timer.timeout.connect(self._on_rebuild_timer_timeout)

        self._refresh_timer = QTimer()
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._on_refresh_timer_timeout)
        self._refresh_clear_cache = self._runtime_state.refresh_clear_cache

        self._last_drag_move_time = self._overlay_state.last_drag_move_time

        self._sync_timer = QTimer()
        self._sync_timer.setSingleShot(True)
        self._sync_timer.timeout.connect(self._do_sync_overlay)
        self._settle_sync_timer = QTimer()
        self._settle_sync_timer.setSingleShot(True)
        self._settle_sync_timer.timeout.connect(self.sync_overlay)

        # Poller that re-attaches the overlay every 500ms
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self.sync_overlay)
        self._poll_timer.start(POLL_INTERVAL_MS)

        cache = GlobalHistoryCache()
        MainMenuWidgetManager._global_cache_instance = cache
        # Auto refreshes from cache lifecycle should not wipe local pinned contexts.
        cache.init_async(callback=lambda: self.refresh(clear_cache=False))
        cache.signals.context_updated.connect(self._on_cache_context_updated)

        # Cache config manager (lazy). Start dirty so first render always pulls
        # profile-resolved values (glass/border opacity) instead of early defaults.
        self._config_manager = None
        self._config_dirty = True
        self._config_profile_name = None

        self._pending_updates = self._runtime_state.pending_updates  # (deck_id, span, history_type, widget_id)
        self._initial_rebuild_queued = self._runtime_state.initial_rebuild_queued
        self._widget_update_signatures = self._runtime_state.widget_update_signatures
        self._last_resize_signature = self._overlay_state.last_resize_signature
        self._review_return_seq = self._runtime_state.review_return_seq
        self._review_return_t0 = self._runtime_state.review_return_t0
        self._skip_next_silent_refresh = self._runtime_state.skip_next_silent_refresh
        self._last_review_deck_id = self._runtime_state.last_review_deck_id
        self._review_return_fast_path = self._runtime_state.review_return_fast_path
        self._review_return_phase_b_active = self._runtime_state.review_return_phase_b_active
        self._last_review_return_rebuild_sig = self._runtime_state.last_review_return_rebuild_sig
        self._last_review_return_rebuild_ts = self._runtime_state.last_review_return_rebuild_ts
        self._op_refresh_timer = QTimer()
        self._op_refresh_timer.setSingleShot(True)
        self._op_refresh_timer.timeout.connect(self._run_operation_refresh)
        self._op_force_refresh = self._runtime_state.op_force_refresh
        self._force_non_blocking_rebuild = self._runtime_state.force_non_blocking_rebuild
        self._last_overview_rebuild_sig = self._runtime_state.last_overview_rebuild_sig
        self._last_browser_rebuild_ts = self._runtime_state.last_browser_rebuild_ts
        self._last_op_callback_rebuild_ts = self._runtime_state.last_op_callback_rebuild_ts
        self._pending_deferred_widget_updates = self._runtime_state.pending_deferred_widget_updates
        self._pending_browser_refresh = self._runtime_state.pending_browser_refresh
        self._pending_partial_refresh_payload = self._runtime_state.pending_partial_refresh_payload
        self._external_refresh_suspensions = self._runtime_state.external_refresh_suspensions
        self._pending_refresh_while_suspended = self._runtime_state.pending_refresh_while_suspended
        self._pending_refresh_clear_cache = self._runtime_state.pending_refresh_clear_cache
        self._last_chart_reflow_sig = self._runtime_state.last_chart_reflow_sig
        self._chart_reflow_epoch = self._runtime_state.chart_reflow_epoch
        self._fade_anims = self._runtime_state.fade_anims
        self._last_h = self._overlay_state.last_h
        self._last_zoom = self._overlay_state.last_zoom
        self._last_placeholder_css_rect = self._overlay_state.last_placeholder_css_rect

    def _on_rebuild_timer_timeout(self) -> None:
        return on_rebuild_timer_timeout_impl(self)

    def _on_refresh_timer_timeout(self) -> None:
        return on_refresh_timer_timeout_impl(self)

    def _widget_allowed_in_context(self, widget_def: dict[str, Any], deck_id: int | None) -> bool:
        return widget_allowed_in_context_impl(
            widget_def=widget_def,
            deck_id=deck_id,
            is_deck_browser=bool(getattr(self, "_is_deck_browser", False)),
        )

    def _review_elapsed_ms(self) -> float | None:
        if self._review_return_t0 is None:
            return None
        return round((time.perf_counter() - self._review_return_t0) * 1000, 1)

    def _mark_config_dirty(self) -> None:
        self._config_dirty = True

    def _get_config_manager(self, force_refresh: bool = False) -> ConfigManager:
        current_profile = getattr(getattr(mw, "pm", None), "name", None) or "default"
        profile_changed = current_profile != getattr(self, "_config_profile_name", None)

        if self._config_manager is None:
            self._config_manager = ConfigManager(mw)
            self._config_dirty = False
            self._config_profile_name = current_profile
            return self._config_manager

        if force_refresh or self._config_dirty or profile_changed:
            self._config_manager = ConfigManager(mw)
            self._config_dirty = False
            self._config_profile_name = current_profile
        return self._config_manager

    def _normalize_time_span(self, span: str, widget_type: str) -> str:
        return normalize_time_span_impl(span, widget_type)

    def _normalized_widget_def(self, widget_def: dict[str, Any]) -> dict[str, Any]:
        return normalized_widget_def_impl(widget_def)

    def _widget_signature(self, widget_def: dict[str, Any], deck_id: int | None, max_ids: tuple[int, int] | None) -> tuple[Any, ...]:
        return widget_signature_impl(widget_def, deck_id, max_ids)

    def register_hooks(self) -> None:
        register_hooks_impl(self)

    def _on_state_did_change(self, new_state, old_state):
        on_state_did_change_impl(self, new_state, old_state)

    def _on_sync_did_finish(self):
        on_sync_did_finish_impl(self)

    def _on_operation_did_execute(self, changes, handler):
        on_operation_did_execute_impl(self, changes, handler)

    def _run_operation_refresh(self):
        run_operation_refresh_impl(self)

    def _on_profile_did_open(self):
        on_profile_did_open_impl(self)

    def _on_internal_theme_changed(self, _source=None):
        on_internal_theme_changed_impl(self, _source=_source)

    def _on_theme_change(self):
        on_theme_change_impl(self)

    def _on_deck_browser_will_render(self, browser, content):
        on_deck_browser_will_render_impl(self, browser, content)

    def _on_overview_will_render(self, overview, content):
        on_overview_will_render_impl(self, overview, content)

    def _on_webview_did_inject_style(self, webview):
        on_webview_did_inject_style_impl(self, webview)

    def _on_reviewer_did_init(self, reviewer):
        on_reviewer_did_init_impl(self, reviewer)

    def _on_reviewer_will_end(self):
        on_reviewer_will_end_impl(self)

    def _get_placeholder_js(self):
        return get_placeholder_js_impl(self)

    def _inject_placeholder(self, content, is_browser):
        inject_placeholder_impl(self, content, is_browser)

    def _on_js_message(self, handled, message, context):
        return on_js_message_impl(self, handled, message, context)

    def eventFilter(self, obj, event):
        return event_filter_impl(self, obj, event, super().eventFilter)

    def _handle_chart_move(self, drop_pos):
        handle_chart_move_impl(self, drop_pos)

    def _finalize_chart_reorder(self):
        finalize_chart_reorder_impl(self)

    def _get_or_create_chart_masonry_row(self, row_idx: int, chart_box: int = 0, box_kind: str = "chart"):
        return get_or_create_chart_masonry_row_impl(self, row_idx, chart_box=chart_box, box_kind=box_kind)

    def _set_chart_rows_animate_moves(self, enabled: bool):
        return set_chart_rows_animate_moves_impl(self, enabled)

    def _run_chart_reflow_animation_pass(self):
        return run_chart_reflow_animation_pass_impl(self)

    def _schedule_chart_reflow_animation(self, pruned_count=0):
        return schedule_chart_reflow_animation_impl(self, pruned_count=pruned_count)

    def _mark_skip_next_show_anim(self, widget):
        return mark_skip_next_show_anim_impl(self, widget)

    def _fade_in_widget(self, widget, duration=CHART_FADE_IN_MS):
        return fade_in_widget_impl(self, widget, duration=duration)

    def _fade_out_widget(self, widget, duration=CHART_FADE_OUT_MS):
        return fade_out_widget_impl(self, widget, duration=duration)

    def _remove_widget_from_chart_rows(self, widget):
        return remove_widget_from_chart_rows_impl(self, widget)

    def _prune_chart_rows(self, valid_widget_ids):
        return prune_chart_rows_impl(self, valid_widget_ids)

    def _schedule_rebuild(self, deck_id: int | None = None, force: bool = False, after_page_load: bool = False) -> None:
        return schedule_rebuild_impl(self, deck_id=deck_id, force=force, after_page_load=after_page_load)

    def _clear_browser_heatmap_snapshot_overlay(self):
        label = getattr(self, "_heatmap_snapshot_label", None)
        if label is not None:
            try:
                label.hide()
            except Exception:
                log_swallowed()
            try:
                label.deleteLater()
            except Exception:
                log_swallowed()
            self._heatmap_snapshot_label = None

    def _rebuild_overlay(self, deck_id: int | None) -> None:
        return rebuild_overlay_impl(self, deck_id)

    def _rebuild_overlay_inner(self, deck_id: int | None) -> None:
        return rebuild_overlay_inner_impl(self, deck_id)
    def _schedule_deferred_widget_update(
        self,
        widget,
        widget_def,
        deck_id,
        signature,
        delay_ms,
        allow_blocking=False,
    ):
        return schedule_deferred_widget_update_impl(
            self,
            widget=widget,
            widget_def=widget_def,
            deck_id=deck_id,
            signature=signature,
            delay_ms=delay_ms,
            allow_blocking=allow_blocking,
        )

    def _get_zoom_factor(self) -> float:
        return get_zoom_factor_impl(self)

    def _apply_zoom_scale_to_widgets(self, zoom):
        return apply_zoom_scale_to_widgets_impl(self, zoom=zoom)

    def _schedule_overlay_sync(self, delay_ms: int = 0) -> None:
        schedule_overlay_sync_impl(self, delay_ms=delay_ms)

    def _run_scheduled_overlay_sync(self) -> None:
        run_scheduled_overlay_sync_impl(self)

    def _update_overlay_geom(self, left, top, width, height):
        update_overlay_geom_impl(self, left, top, width, height)

    def _current_resize_signature(self, width):
        return current_resize_signature_impl(self, width)

    def _resize_overlay(self, force_refresh_blur: bool = False) -> None:
        resize_overlay_impl(self, force_refresh_blur=force_refresh_blur)

    def _update_placeholder_height(self, h):
        update_placeholder_height_impl(self, h)

    def _trigger_async_widget_update(self, widget, widget_def, deck_id):
        return trigger_async_widget_update_impl(self, widget=widget, widget_def=widget_def, deck_id=deck_id)

    def sync_overlay(self) -> None:
        """Update overlay geometry based on placeholder positions in the webview (Debounced)."""
        sync_overlay_impl(self)

    def _do_sync_overlay(self) -> None:
        do_sync_overlay_impl(self)

    def _show_context_menu(self, widget, widget_id, pos):
        show_context_menu_impl(self, widget, widget_id, pos)

    def _open_details_dialog(self):
        open_details_dialog_impl()

    def _open_time_span_settings(self):
        open_time_span_settings_impl(self)

    def _open_widget_settings(self, widget, widget_def):
        open_widget_settings_impl(self, widget, widget_def)

    def _update_span(self, wid, span):
        update_span_impl(self, wid, span)

    def _update_span_bulk(self, wid, updates):
        update_span_bulk_impl(self, wid, updates)

    def _update_setting(self, wid, key, value):
        update_setting_impl(self, wid, key, value)

    def _toggle_global_bottom_stats(self, enabled):
        toggle_global_bottom_stats_impl(self, enabled)

    def _toggle_global_show_stats(self, enabled):
        toggle_global_show_stats_impl(self, enabled)

    def _unpin(self, wid):
        unpin_impl(self, wid)

    def _reset_widget_size(self, wid):
        reset_widget_size_impl(self, wid)

    def _on_cache_context_updated(self):
        return on_cache_context_updated_impl(self)

    def _drain_pending_partial_refresh(self):
        return drain_pending_partial_refresh_impl(self)

    def _apply_partial_widget_refresh(self, deck_ids, reason):
        return apply_partial_widget_refresh_impl(self, deck_ids=deck_ids, reason=reason)

    def refresh(self, clear_cache: bool = True) -> None:
        return refresh_impl(self, clear_cache=clear_cache)

    def set_external_refresh_suspended(self, suspended: bool, reason: str = "external"):
        return set_external_refresh_suspended_impl(self, suspended=suspended, reason=reason)

    def update_styles(self, config_manager: ConfigManager | None = None) -> None:
        return update_styles_impl(self, config_manager=config_manager)


