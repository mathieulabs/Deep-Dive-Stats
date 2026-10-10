# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Keep the Deep Dive heatmap on the selected period (and on the zoomed range)."""
from datetime import datetime, timedelta

from ....logic.heatmap import anchor_heatmap_mode_state, normalize_heatmap_mode_state


def range_last_day(history_range, custom_days=7, custom_type="relative", start_date_str="", end_date_str=""):
    """Last Anki day covered by a Deep Dive period (e.g. Dec 31 for 'Last year')."""
    try:
        from ....logic import rollover_hour
        from ....logic.data.core.time_utils import get_time_range_ms

        _s, end_ms, _ps, _pe = get_time_range_ms(
            int(history_range),
            0,
            custom_days=custom_days,
            custom_type=custom_type,
            start_date_str=start_date_str,
            end_date_str=end_date_str,
        )
        return (datetime.fromtimestamp((int(end_ms) - 1) / 1000.0) - timedelta(hours=rollover_hour())).date()
    except Exception:
        return None


def resolve_heatmap_state(manager, current_mode, anchor_date, now=None):
    """Return (year, end_365, target_end) for the Deep Dive heatmap.

    The heatmap only jumps to anchor_date when the anchor changes (new period or
    zoom), so a year browsed with the arrows survives unrelated refreshes.
    """
    key = (current_mode, anchor_date)
    if anchor_date is not None and getattr(manager, "_hm_anchor_key", None) != key:
        manager._hm_anchor_key = key
        return anchor_heatmap_mode_state(
            current_mode,
            anchor_date,
            getattr(manager, "heatmap_year", None),
            getattr(manager, "end_date_365", None),
            now=now,
        )
    return normalize_heatmap_mode_state(
        current_mode,
        getattr(manager, "heatmap_year", None),
        getattr(manager, "end_date_365", None),
        now=now,
    )
