# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
PINNED_VALUE_FS = 14.5
PINNED_TITLE_FS = 7.5
PINNED_SUBTITLE_FS = 8.25
PINNED_H_MARGIN = 12
PINNED_BASE_HEIGHT = 66

DASHBOARD_VALUE_FS = 15.0
DASHBOARD_TITLE_FS = 6.8
DASHBOARD_SUBTITLE_FS = 7.0
DASHBOARD_H_MARGIN = 8
DASHBOARD_THRESHOLD_MULTIPLIER = 1.2
DASHBOARD_MIN_FIT_SCALE = 0.4
DASHBOARD_MAX_FIT_SCALE = 1.0
DASHBOARD_FIT_EXPONENT = 1.6
DASHBOARD_FIT_VALUE_BASE = 5.5
DASHBOARD_FIT_VALUE_GAIN = 7.0
DASHBOARD_FIT_TITLE_BASE = 3.5
DASHBOARD_FIT_TITLE_GAIN = 2.7
DASHBOARD_FIT_SUB_MULT = 0.5
DASHBOARD_FIT_SUB_BASE = 2.0
DASHBOARD_FIT_MARGIN_BASE = 3
DASHBOARD_FIT_MARGIN_GAIN = 5
DASHBOARD_GROW_EXPONENT = 0.5
DASHBOARD_MAX_GROW = 1.3  # low on purpose: the cards must not take much more room
DASHBOARD_BASE_HEIGHT_NORMAL = 32
DASHBOARD_BASE_HEIGHT_REDUCED = 14
DASHBOARD_HEIGHT_GAIN = 32


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


def dashboard_typography(scale, width, total_ideal, reduced_height_mode):
    user_scale = max(0.5, min(1.8, float(scale or 1.0)))
    threshold_w = float(total_ideal) * DASHBOARD_THRESHOLD_MULTIPLIER
    if width < threshold_w and width > 0:
        fit_scale = max(DASHBOARD_MIN_FIT_SCALE, min(DASHBOARD_MAX_FIT_SCALE, width / threshold_w))
        adj_scale = fit_scale ** DASHBOARD_FIT_EXPONENT
        val_fs = DASHBOARD_FIT_VALUE_BASE + (DASHBOARD_FIT_VALUE_GAIN * adj_scale)
        title_fs = DASHBOARD_FIT_TITLE_BASE + (DASHBOARD_FIT_TITLE_GAIN * adj_scale)
        sub_fs = (val_fs * DASHBOARD_FIT_SUB_MULT) + DASHBOARD_FIT_SUB_BASE
        h_margin = DASHBOARD_FIT_MARGIN_BASE + (DASHBOARD_FIT_MARGIN_GAIN * adj_scale)
    else:
        adj_scale = 1.0
        val_fs = DASHBOARD_VALUE_FS
        title_fs = DASHBOARD_TITLE_FS
        sub_fs = DASHBOARD_SUBTITLE_FS
        h_margin = DASHBOARD_H_MARGIN
        if threshold_w > 0 and width > threshold_w:
            # Room to spare (wide window): one factor for fonts, margins and height together.
            user_scale *= min(DASHBOARD_MAX_GROW, (width / threshold_w) ** DASHBOARD_GROW_EXPONENT)

    base_h = DASHBOARD_BASE_HEIGHT_REDUCED if bool(reduced_height_mode) else DASHBOARD_BASE_HEIGHT_NORMAL
    targ_h = (base_h + (DASHBOARD_HEIGHT_GAIN * adj_scale)) * user_scale
    return {
        "threshold_w": threshold_w,
        "val_fs": val_fs * user_scale,
        "title_fs": title_fs * user_scale,
        "sub_fs": sub_fs * user_scale,
        "h_margin": h_margin * user_scale,
        "targ_h": targ_h,
    }


def ideal_measure_font_sizes(is_pinned, *, scale=1.0, title_multiplier=1.0):
    """Canonical font sizes used when measuring preferred card width."""
    if is_pinned:
        value_fs = PINNED_VALUE_FS
        title_fs = PINNED_TITLE_FS
    else:
        value_fs = DASHBOARD_VALUE_FS
        title_fs = DASHBOARD_TITLE_FS

    return {
        "value_fs": float(value_fs) * float(scale),
        "title_fs": float(title_fs) * float(title_multiplier) * float(scale),
    }
