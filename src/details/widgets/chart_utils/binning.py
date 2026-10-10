# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""
Centralized binning logic for charts to group days when time spans are large.
"""
import time

_BINNING_LEVEL_CACHE = {
    "value": "normal",
    "ts": 0.0,
}
_BINNING_LEVEL_CACHE_TTL_S = 0.75
_BINNING_SCALE_MIN = 50
_BINNING_SCALE_MAX = 200

def invalidate_binning_level_cache():
    """Force next get_bin_size() to reload current level from config."""
    _BINNING_LEVEL_CACHE["ts"] = 0.0


def _read_global_binning_level():
    now = time.monotonic()
    if (now - float(_BINNING_LEVEL_CACHE.get("ts", 0.0))) <= _BINNING_LEVEL_CACHE_TTL_S:
        return int(_BINNING_LEVEL_CACHE.get("value", 100))
    scale = 100
    try:
        from aqt import mw
        from ....config import ConfigManager
        from ....const import Config
        if mw is not None:
            cfg = ConfigManager(mw).config
            scale = int(cfg.get(Config.CHART_BINNING_SCALE, 100))
    except Exception:
        scale = 100
    scale = max(_BINNING_SCALE_MIN, min(_BINNING_SCALE_MAX, int(scale)))
    _BINNING_LEVEL_CACHE["value"] = scale
    _BINNING_LEVEL_CACHE["ts"] = now
    return scale


# Natural groupings: day, 2 days, 3 days, week, 2 weeks, month, 2 months, 3 months.
_BIN_LADDER = (1, 2, 3, 7, 14, 30, 60, 90)


def scale_to_step(scale):
    """Saved scale (50 to 200) to a step on the ladder, from -2 to +2."""
    s = int(scale)
    if s <= 60:
        return -2
    if s < 90:
        return -1
    if s <= 110:
        return 0
    if s <= 170:
        return 1
    return 2


def _apply_binning_level(base_bin_size):
    base = max(1, int(base_bin_size))
    step = scale_to_step(_read_global_binning_level())
    if step == 0:
        return base
    try:
        pos = _BIN_LADDER.index(base)
    except ValueError:
        pos = min(range(len(_BIN_LADDER)), key=lambda i: abs(_BIN_LADDER[i] - base))
    pos = max(0, min(len(_BIN_LADDER) - 1, pos + step))
    return _BIN_LADDER[pos]


def get_bin_size(days_count):
    """
    Returns the number of days to group into a single bar/point based on total range.
    Follows Anki-like natural groupings.
    """
    if days_count <= 31: # 1 month
        base = 1
    elif days_count <= 90: # 3 months
        base = 2
    elif days_count <= 185: # 6 months
        base = 3
    elif days_count <= 366: # 1 year
        base = 7
    elif days_count <= 730: # 2 years
        base = 14
    elif days_count <= 1850: # 5 years
        base = 30
    elif days_count <= 3650: # 10 years
        base = 60
    else: # Very long term
        base = 90
    return _apply_binning_level(base)

