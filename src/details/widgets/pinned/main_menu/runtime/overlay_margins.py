# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Margins around the pinned widgets overlay (left/right share one value)."""

from .....ui import Config

DEFAULT_SIDE = 20
DEFAULT_TOP = 0
DEFAULT_BOTTOM = 20
DEFAULT_SECTION_SPACING = 10
MAX_MARGIN = 200


def _clamped(conf, key, default):
    try:
        return max(0, min(MAX_MARGIN, int(conf.get(key, default))))
    except Exception:
        return default


# -- the spaces between boxes and between lines --------------------------------------
# Each one can be changed by dragging it (pinned.js). Changed ones are kept in
# Config.PINNED_GAPS by key: "box:<box above>" for the space under a box, and
# "line:<box>:<line index>" for the space under a line of a box. The others use the
# default: the "Space Between Lines" setting, the same for every space (between two lines
# of a box or between two boxes: on screen, both are just two lines).

MAX_GAP = 200


def gap_px(conf, key, default):
    try:
        value = (conf.get(Config.PINNED_GAPS) or {}).get(key)
        if value is None:
            return int(default)
        return max(0, min(MAX_GAP, int(value)))
    except Exception:
        return int(default)


def section_gap_default(conf):
    return _clamped(conf, Config.PINNED_SECTION_SPACING, DEFAULT_SECTION_SPACING)


