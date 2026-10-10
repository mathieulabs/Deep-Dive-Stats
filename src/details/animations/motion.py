# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from ...const import Config

MODE_ALL = "all"
MODE_NO_PINNED = "no_pinned"
MODE_NO_DETAILS = "no_details"
MODE_NONE = "none"
_VALID = {MODE_ALL, MODE_NO_PINNED, MODE_NO_DETAILS, MODE_NONE}

def get_animation_scope() -> str:
    """Return the active animation scope mode."""
    try:
        from ...config import read_config_value
        scope = str(read_config_value(Config.ANIMATION_SCOPE, "") or "").strip().lower()
        if scope in _VALID:
            return scope
        return MODE_ALL
    except Exception:
        return MODE_ALL


def animations_enabled(scope: str = "all") -> bool:
    """Whether animations are enabled for a scope.

    scope is "pinned" (main menu widgets), "details" (Deep Dive window) or "all".
    """
    mode = get_animation_scope()
    if mode == MODE_ALL:
        return True
    if mode == MODE_NONE:
        return False
    scope = str(scope or "all").strip().lower()
    if scope == "pinned":
        return mode != MODE_NO_PINNED
    if scope == "details":
        return mode != MODE_NO_DETAILS
    return True

