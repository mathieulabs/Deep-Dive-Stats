# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RuntimeState:
    refresh_clear_cache: bool = False
    pending_updates: set[tuple[Any, ...]] = field(default_factory=set)
    initial_rebuild_queued: bool = False
    widget_update_signatures: dict[Any, Any] = field(default_factory=dict)
    review_return_seq: int = 0
    review_return_t0: float | None = None
    skip_next_silent_refresh: bool = False
    last_review_deck_id: int | None = None
    review_return_fast_path: bool = False
    review_return_phase_b_active: bool = False
    last_review_return_rebuild_sig: tuple[int | None, str] | None = None
    last_review_return_rebuild_ts: float = 0.0
    op_force_refresh: bool = False
    force_non_blocking_rebuild: bool = False
    last_overview_rebuild_sig: tuple[int | None, float] = (None, 0.0)
    last_browser_rebuild_ts: float = 0.0
    last_op_callback_rebuild_ts: float = 0.0
    pending_deferred_widget_updates: set[tuple[Any, ...]] = field(default_factory=set)
    pending_browser_refresh: bool = False
    pending_partial_refresh_payload: Any = None
    external_refresh_suspensions: set[str] = field(default_factory=set)
    pending_refresh_while_suspended: bool = False
    pending_refresh_clear_cache: bool = False
    last_chart_reflow_sig: Any = None
    chart_reflow_epoch: int = 0
    fade_anims: dict[Any, Any] = field(default_factory=dict)
    rebuild_in_progress: bool = False
    scheduled_deck_id: int | None = None
    current_deck_id: int | None = None
    is_deck_browser: bool = True


@dataclass(slots=True)
class OverlayState:
    last_geom: tuple[int, int, int, int, float] | None = None
    last_resize_signature: Any = None
    last_drag_move_time: float = 0.0
    last_h: float = -1.0
    last_zoom: float | None = None
    last_placeholder_css_rect: tuple[float, float, float, float] | None = None


