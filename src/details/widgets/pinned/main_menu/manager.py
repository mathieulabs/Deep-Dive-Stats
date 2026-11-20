# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The pinned widgets' link to Anki, behind the web block (web_ui/pinned.py) that draws them.

It keeps the history cache and the pinned data fresh: after a review (runtime/navigation_flow.py), an edit or a sync
(runtime/hook_events.py), a profile opened. It also holds the config the menus and dialogs of the widgets write to,
and runs their actions (ui/context_actions.py)."""
from __future__ import annotations

from typing import Any, ClassVar

from aqt import mw
from aqt.qt import QObject, QTimer

from .state import RuntimeState


class MainMenuWidgetManager(QObject):
    _instance: ClassVar["MainMenuWidgetManager | None"] = None
    _last_max_ids: ClassVar[tuple[int, int] | None] = None

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
        s = RuntimeState()
        self._current_deck_id = s.current_deck_id
        self._is_deck_browser = s.is_deck_browser
        # the review return (runtime/navigation_flow.py)
        self._review_return_seq = s.review_return_seq
        self._review_return_t0 = s.review_return_t0
        self._review_return_fast_path = s.review_return_fast_path
        self._review_return_phase_b_active = s.review_return_phase_b_active
        self._last_review_deck_id = s.last_review_deck_id
        # an edit's refresh, coalesced (runtime/hook_events.py)
        self._op_force_refresh = s.op_force_refresh
        self._op_refresh_timer = QTimer()
        self._op_refresh_timer.setSingleShot(True)
        self._op_refresh_timer.timeout.connect(self._run_operation_refresh)
        from .ui.context_menu import PinnedContextMenu

        self._context_menu = PinnedContextMenu(self)
        # The config (lazy). Starts dirty so the first read has the profile's values, not early defaults.
        self._config_manager = None
        self._config_dirty = True
        self._config_profile_name = None
        from ....logic.history_cache import GlobalHistoryCache

        GlobalHistoryCache().init_async()

    # the config ---------------------------------------------------------------------------------------------------
    def _mark_config_dirty(self) -> None:
        self._config_dirty = True

    def _get_config_manager(self, force_refresh: bool = False):
        from .....config import ConfigManager

        current_profile = getattr(getattr(mw, "pm", None), "name", None) or "default"
        if (
            self._config_manager is None
            or force_refresh
            or self._config_dirty
            or current_profile != self._config_profile_name
        ):
            self._config_manager = ConfigManager(mw)
            self._config_dirty = False
            self._config_profile_name = current_profile
        return self._config_manager

    def _normalized_widget_def(self, widget_def: dict[str, Any]) -> dict[str, Any]:
        from .ui.widget_defs import normalized_widget_def

        return normalized_widget_def(widget_def)

    # Anki's hooks -------------------------------------------------------------------------------------------------
    def register_hooks(self) -> None:
        from .runtime.hook_events import register_hooks

        register_hooks(self)

    def _on_state_did_change(self, new_state, old_state):
        from .runtime.navigation_flow import on_state_did_change

        on_state_did_change(self, new_state, old_state)

    def _on_reviewer_did_init(self, reviewer):
        from .runtime.navigation_flow import on_reviewer_did_init

        on_reviewer_did_init(self, reviewer)

    def _on_sync_did_finish(self):
        from .runtime.hook_events import on_sync_did_finish

        on_sync_did_finish(self)

    def _on_operation_did_execute(self, changes, handler):
        from .runtime.hook_events import on_operation_did_execute

        on_operation_did_execute(self, changes, handler)

    def _run_operation_refresh(self):
        from .runtime.hook_events import run_operation_refresh

        run_operation_refresh(self)

    def _on_profile_did_open(self):
        from .runtime.hook_events import on_profile_did_open

        on_profile_did_open(self)

    def _on_theme_change(self):
        from .runtime.hook_events import on_theme_change

        on_theme_change(self)


    # what the menus, the dialogs and the settings call --------------------------------------------------------------
    def refresh(self, clear_cache: bool = True) -> None:
        """The settings or the data changed: the pinned data is read again (the web block redraws itself on the
        config's save, web_ui/pinned.py). Nothing while reviewing, nor during the review return, which clears it
        itself once the history cache is fresh."""
        if not clear_cache or mw.state not in ("deckBrowser", "overview") or self._review_return_fast_path:
            return
        from ..widget_factory.utils import PinnedDataManager

        PinnedDataManager.clear()

    def update_styles(self, config_manager=None) -> None:
        """The look changed (the settings' live preview): the web block's boxes restyled."""
        from .....web_ui.pinned import enabled, preview_styles

        if enabled():
            preview_styles(config_manager)

    def _open_time_span_settings(self):
        from .ui.context_actions import open_time_span_settings

        open_time_span_settings(self)

    def _open_widget_settings(self, widget, widget_def):
        from .ui.context_actions import open_widget_settings

        open_widget_settings(self, widget, widget_def)

    def _update_span_bulk(self, wid, updates):
        from .ui.context_actions import update_span_bulk

        update_span_bulk(self, wid, updates)

    def _update_setting(self, wid, key, value):
        from .ui.context_actions import update_setting

        update_setting(self, wid, key, value)

    def _toggle_global_bottom_stats(self, enabled):
        from .ui.context_actions import toggle_global_bottom_stats

        toggle_global_bottom_stats(self, enabled)

    def _toggle_global_show_stats(self, enabled):
        from .ui.context_actions import toggle_global_show_stats

        toggle_global_show_stats(self, enabled)

    def _unpin(self, wid):
        from .ui.context_actions import unpin

        unpin(self, wid)

    def _reset_widget_size(self, wid):
        from .ui.context_actions import reset_widget_size

        reset_widget_size(self, wid)


# The id Onigiri keeps the block's place under in its own config (web_ui/onigiri.py): the name of the deck list hook
# of the native overlay that came before, kept as it was so a block placed in Onigiri stays where it is.
ONIGIRI_HOOK_ID = f"{__name__}._on_deck_browser_will_render"
