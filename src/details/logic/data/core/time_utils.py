# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Time range calculation utilities for data loading."""

from datetime import datetime, timedelta
from aqt.qt import QDate, Qt
from ... import LAST_YEAR, Period, rollover_hour
from ...logger import log_swallowed
from .abs_period import is_abs, decode as decode_abs


def get_time_range_ms(range_type, week_start, custom_days=7, custom_type="relative",
                      start_date_str="", end_date_str="", show_trends=False):
    """
    Calculate start_ms, end_ms, prev_start_ms, prev_end_ms based on range type.
    Ranges are rolling windows ending with the current logical day, so `week_start` is not
    used; it stays in the signature because callers pass it.
    """
    # Rollover-aligned end of the current logical day.
    off_h = rollover_hour()
    now = datetime.now()

    today_rollover = now.replace(hour=off_h, minute=0, second=0, microsecond=0)

    if now >= today_rollover:
        # Currently in today's logical day -> ends at tomorrow's rollover
        anki_day_end_dt = today_rollover + timedelta(days=1)
    else:
        # Currently in yesterday's logical day -> ends at today's rollover
        anki_day_end_dt = today_rollover

    ms_per_day = 86400000

    # anki_day_start_dt is the rollover boundary that started the CURRENT logical day
    anki_day_start_dt = anki_day_end_dt - timedelta(days=1)

    end_ms = int(anki_day_end_dt.timestamp() * 1000)
    anchor_ms = int(anki_day_start_dt.timestamp() * 1000)

    start_ms = 0

    if is_abs(range_type):
        d0, d1 = decode_abs(range_type)
        start_ms = int(datetime(d0.year, d0.month, d0.day, off_h, 0).timestamp() * 1000)
        end_ms = int((datetime(d1.year, d1.month, d1.day, off_h, 0) + timedelta(days=1)).timestamp() * 1000) - 1
    elif range_type == Period.TOTAL:
        start_ms = 0
    elif range_type == Period.TODAY:
        start_ms = anchor_ms
    elif range_type == Period.YESTERDAY:
        start_ms = anchor_ms - 86400000
        end_ms = anchor_ms
    elif range_type == Period.WEEK:
        # Days total: 6 previous days + the current logical day
        start_ms = anchor_ms - (6 * 86400000)
    elif range_type == Period.TWO_WEEKS:
        start_ms = anchor_ms - (13 * 86400000)
    elif range_type == Period.MONTH:
        start_ms = anchor_ms - (29 * 86400000)
    elif range_type == Period.THREE_MONTHS:
        start_ms = anchor_ms - (89 * 86400000)
    elif range_type == Period.YEAR:
        start_ms = anchor_ms - (364 * 86400000)
    elif range_type == LAST_YEAR:
        last_year = anki_day_start_dt.year - 1
        start_ms = int(datetime(last_year, 1, 1, off_h, 0).timestamp() * 1000)
        end_ms = int(datetime(last_year + 1, 1, 1, off_h, 0).timestamp() * 1000) - 1
    elif range_type == Period.CUSTOM:
        if custom_type in ("absolute", "exact"):  # "exact" = bounds of a previous period (trends)
            off_h = rollover_hour()
            if start_date_str:
                try:
                    sd = QDate.fromString(start_date_str, Qt.DateFormat.ISODate)
                    start_dt = datetime(sd.year(), sd.month(), sd.day(), off_h, 0, 0)
                    start_ms = int(start_dt.timestamp() * 1000)
                except Exception:
                    start_ms = 0
            if end_date_str:
                try:
                    ed = QDate.fromString(end_date_str, Qt.DateFormat.ISODate)
                    # Next day's rollover minus 1ms
                    end_dt = datetime(ed.year(), ed.month(), ed.day(), off_h, 0, 0) + timedelta(days=1)
                    end_ms = int(end_dt.timestamp() * 1000) - 1
                except Exception:
                    log_swallowed()
        else:
            start_ms = anchor_ms - (custom_days * ms_per_day)
    elif isinstance(range_type, int) and range_type > 7:
        # Anki logical day starts at rollover
        off_h = rollover_hour()
        # Jan 1st of Year N at rollover hour
        start_ms = int(datetime(range_type, 1, 1, off_h, 0).timestamp() * 1000)
        # Jan 1st of Year N+1 at rollover hour minus 1ms
        end_ms = int(datetime(range_type + 1, 1, 1, off_h, 0).timestamp() * 1000) - 1

    prev_start_ms = 0
    prev_end_ms = 0
    if show_trends:
        duration = end_ms - start_ms
        prev_end_ms = start_ms
        prev_start_ms = start_ms - duration
        # Calendar years have different lengths (leap years): compare a calendar
        # year with the whole previous calendar year instead of 'same duration'.
        try:
            cal_year = None
            if range_type == LAST_YEAR:
                cal_year = anki_day_start_dt.year - 1
            elif isinstance(range_type, int) and range_type >= 1900:
                cal_year = range_type
            if cal_year is not None:
                prev_start_ms = int(datetime(cal_year - 1, 1, 1, rollover_hour(), 0).timestamp() * 1000)
        except Exception:
            log_swallowed()

    return start_ms, end_ms, prev_start_ms, prev_end_ms


def custom_exact_date_bounds_from_ms(start_ms: int, end_ms: int, rollover_hour: int) -> tuple[str, str]:
    """Convert [start_ms, end_ms) range to exact custom-date bounds used by cache lookups."""
    start_date = (
        datetime.fromtimestamp(start_ms / 1000) - timedelta(hours=rollover_hour)
    ).strftime("%Y-%m-%d")
    end_date = (
        datetime.fromtimestamp((end_ms - 1) / 1000) - timedelta(hours=rollover_hour)
    ).strftime("%Y-%m-%d")
    return start_date, end_date


