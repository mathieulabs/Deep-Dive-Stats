# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from datetime import datetime, timedelta

from .. import day_end_with_rollover


def get_heatmap_year_end(target_year):
    return datetime(int(target_year), 12, 31, 23, 59, 59)


def get_heatmap_365_end_date(target_year, now=None):
    current_now = now or datetime.now()
    target_year = int(target_year)
    if target_year == current_now.year:
        return day_end_with_rollover(current_now)
    return get_heatmap_year_end(target_year)


def _resolve_base_year(current_mode, heatmap_year, end_date_365=None, now=None):
    current_now = now or datetime.now()
    if current_mode == "365" and end_date_365 is not None:
        return int(end_date_365.year)
    if heatmap_year is not None:
        return int(heatmap_year)
    return int(current_now.year)


def normalize_heatmap_mode_state(current_mode, heatmap_year=None, end_date_365=None, now=None):
    current_now = now or datetime.now()
    base_year = _resolve_base_year(current_mode, heatmap_year, end_date_365=end_date_365, now=current_now)

    if current_mode == "365":
        resolved_end_365 = end_date_365 or get_heatmap_365_end_date(base_year, now=current_now)
        return int(resolved_end_365.year), resolved_end_365, resolved_end_365

    if current_mode == "year":
        return int(base_year), end_date_365, get_heatmap_year_end(base_year)

    return int(base_year), end_date_365, current_now


def switch_heatmap_mode_state(current_mode, new_mode, heatmap_year=None, end_date_365=None, now=None):
    current_now = now or datetime.now()
    current_year = int(current_now.year)
    current_end_365 = get_heatmap_365_end_date(current_year, now=current_now)

    # Mode switches always re-anchor to "now"/the current year so Deep Dive and
    # Pinned share the same UX regardless of the previously browsed year/window.
    if new_mode == "365":
        return current_year, current_end_365, current_end_365

    if new_mode == "year":
        return current_year, current_end_365, get_heatmap_year_end(current_year)

    return current_year, current_end_365, current_now


def step_heatmap_mode_state(current_mode, heatmap_year=None, delta=0, end_date_365=None, now=None):
    current_now = now or datetime.now()
    base_year = _resolve_base_year(current_mode, heatmap_year, end_date_365=end_date_365, now=current_now)

    if current_mode == "365":
        base_end_365 = end_date_365 or get_heatmap_365_end_date(base_year, now=current_now)
        next_end_365 = base_end_365 + timedelta(days=365 * int(delta))
        return int(next_end_365.year), next_end_365, next_end_365

    next_year = int(base_year) + int(delta)
    return int(next_year), end_date_365, get_heatmap_year_end(next_year)


def anchor_heatmap_mode_state(current_mode, anchor_date, heatmap_year=None, end_date_365=None, now=None):
    """Heatmap state showing anchor_date, the last day of the selected period or zoom.

    Year view shows that day's year, 365 view the 365 days ending that day. An
    anchor on or after today keeps the usual "today" state.
    """
    from .. import rollover_hour

    current_now = now or datetime.now()
    if current_mode not in ("year", "365") or anchor_date is None:
        return normalize_heatmap_mode_state(current_mode, heatmap_year, end_date_365, now=current_now)
    logical_today = (day_end_with_rollover(current_now) - timedelta(hours=rollover_hour())).date()
    if anchor_date >= logical_today:
        return switch_heatmap_mode_state(current_mode, current_mode, now=current_now)
    if current_mode == "year":
        return int(anchor_date.year), end_date_365, get_heatmap_year_end(anchor_date.year)
    end = datetime(anchor_date.year, anchor_date.month, anchor_date.day, 23, 59, 59)
    return int(end.year), end, end
