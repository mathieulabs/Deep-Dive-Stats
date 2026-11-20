# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""
Centralized binning logic for charts to group days when time spans are large.
"""

_BINNING_LEVEL_CACHE = {
    "value": "normal",
    "ts": 0.0,
}

def invalidate_binning_level_cache():
    """Force next get_bin_size() to reload current level from config."""
    _BINNING_LEVEL_CACHE["ts"] = 0.0


