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


TRANSITION_MORPH = "morph"
TRANSITION_FADE = "fade"
TRANSITION_NONE = "none"


def transition_style(scope: str = "details") -> str:
    """How the charts take new data (deck or period change) in scope ("details", the Deep
    Dive, or "pinned"): "morph", each chart animating from its old data, "fade", its old
    picture fading into the new one (much lighter), or "none", the new data shown at once.
    In the Deep Dive, cards that come or go glide and fade unless it is "none"."""
    key = Config.PINNED_TRANSITION_STYLE if str(scope) == "pinned" else Config.DEEP_DIVE_TRANSITION_STYLE
    try:
        from ...config import read_config_value
        style = str(read_config_value(key, "") or "").strip().lower()
        return style if style in (TRANSITION_FADE, TRANSITION_NONE) else TRANSITION_MORPH
    except Exception:
        return TRANSITION_MORPH



def _flag(key) -> bool:
    try:
        from ...config import read_config_value
        value = read_config_value(key, True)
        return True if value is None else bool(value)
    except Exception:
        return True


def appear_animated() -> bool:
    """Whether the charts grow in when they first show (else they show at once)."""
    return _flag(Config.CHART_APPEAR_ANIMATION)


def zoom_animated() -> bool:
    """Whether a zoom glides to its new range (else it jumps there)."""
    return _flag(Config.ZOOM_ANIMATION)
