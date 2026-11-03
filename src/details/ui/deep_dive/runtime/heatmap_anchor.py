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


def zoom_year_anchor(first_day, last_day):
    """Anchor day for the year view of a zoomed range: its last day, or Dec 31 of an
    earlier year holding more of the range (a zoom from late November to January 1
    shows the November-December year, not a year with one day of it)."""
    if first_day is None or last_day is None or first_day.year >= last_day.year:
        return last_day
    from datetime import date

    best_year, best_days = last_day.year, -1
    for year in range(first_day.year, last_day.year + 1):
        lo = max(first_day, date(year, 1, 1))
        hi = min(last_day, date(year, 12, 31))
        days = (hi - lo).days + 1
        if days >= best_days:  # a tie goes to the later year
            best_year, best_days = year, days
    return last_day if best_year == last_day.year else date(best_year, 12, 31)


CONTINUOUS_MONTHS_BEFORE = 4  # the continuous view shows 4 months each side of its center
CONTINUOUS_MONTHS_AFTER = 4


def continuous_offset_for_zoom(first_day, last_day, current_offset, now=None):
    """Month offset for the continuous view (see HeatmapWidget.cont_month_offset) after a
    zoom on first_day .. last_day. A range ending today or later: the usual view. A range
    still in the months on screen: no move. Else the view slides so the range's last
    month is its last column, like the 365 view ending on the zoom's last day."""
    from ....logic import day_end_with_rollover, rollover_hour

    if last_day is None:
        return current_offset
    day_end = day_end_with_rollover(now)
    logical_today = (day_end - timedelta(hours=rollover_hour())).date()
    if last_day >= logical_today:
        return 0
    # Month numbers as the widget counts them (it centers on day_end's month).
    center = day_end.year * 12 + (day_end.month - 1)
    end_m = last_day.year * 12 + (last_day.month - 1)
    start_m = (first_day.year * 12 + (first_day.month - 1)) if first_day is not None else end_m
    lo = center + int(current_offset) - CONTINUOUS_MONTHS_BEFORE
    hi = center + int(current_offset) + CONTINUOUS_MONTHS_AFTER
    if lo <= start_m and end_m <= hi:
        return current_offset
    return end_m - CONTINUOUS_MONTHS_AFTER - center
