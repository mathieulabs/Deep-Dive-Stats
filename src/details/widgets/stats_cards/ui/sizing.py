# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
PINNED_VALUE_FS = 14.5
PINNED_TITLE_FS = 7.5
PINNED_SUBTITLE_FS = 8.25
PINNED_H_MARGIN = 12
PINNED_BASE_HEIGHT = 66


def normalize_scale_percent(scale_pct, *, default=100):
    """Return a clamped scale percent used by stat-card containers."""
    try:
        val = float(scale_pct)
    except Exception:
        val = float(default)
    return max(50.0, min(180.0, val))


def scale_ratio_from_percent(scale_pct, *, default=100):
    """Convert a percentage scale to a ratio with clamping."""
    return normalize_scale_percent(scale_pct, default=default) / 100.0


def compact_typography(scale):
    return {
        "targ_h": PINNED_BASE_HEIGHT * scale,
        "val_fs": PINNED_VALUE_FS * scale,
        "title_fs": PINNED_TITLE_FS * scale,
        "sub_fs": PINNED_SUBTITLE_FS * scale,
        "h_margin": PINNED_H_MARGIN * scale,
    }


