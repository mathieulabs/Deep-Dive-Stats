# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class RuntimeState:
    review_return_seq: int = 0
    review_return_t0: float | None = None
    last_review_deck_id: int | None = None
    review_return_fast_path: bool = False
    review_return_phase_b_active: bool = False
    op_force_refresh: bool = False
    current_deck_id: int | None = None
    is_deck_browser: bool = True


