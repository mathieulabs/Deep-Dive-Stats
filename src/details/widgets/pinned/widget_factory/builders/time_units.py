# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Show a duration in the unit the user picked (seconds, minutes, hours, days)."""
from ....chart_utils.formatting import fmt_num

UNIT_TOKENS: dict = {
    "s": "s", "sec": "s", "second": "s", "seconds": "s",
    "min": "min", "m": "min", "minute": "min", "minutes": "min",
    "h": "h", "hr": "h", "hour": "h", "hours": "h",
    "d": "d", "day": "d", "days": "d",
}
# (value, label) for settings combos; "auto" keeps the default text.
UNIT_CHOICES: tuple = (("auto", "Auto"), ("s", "Seconds"), ("min", "Minutes"), ("h", "Hours"), ("d", "Days"))
_UNIT_SECONDS = {"s": 1.0, "min": 60.0, "h": 3600.0, "d": 86400.0}
_UNIT_SUFFIX = {"s": "s", "min": " min", "h": "h", "d": "d"}
# stat field -> (raw key in the stat map, unit of that raw number)
TIME_RAW: dict = {
    "total_time": ("_raw_total_time_h", "h"),
    "time_per_day": ("_raw_time_per_day_h", "h"),
    "avg_time": ("_raw_avg_time_s", "s"),
}


def apply_time_unit(field, unit_token, raw_values, precision):
    """Return the duration of `field` in the requested unit, or None to keep the default text."""
    unit = UNIT_TOKENS.get(str(unit_token or "").strip().lower())
    spec = TIME_RAW.get(field)
    if unit is None or spec is None:
        return None
    raw = (raw_values or {}).get(spec[0])
    if raw is None:
        return None
    seconds = float(raw) * _UNIT_SECONDS[spec[1]]
    return f"{fmt_num(seconds / _UNIT_SECONDS[unit], precision)}{_UNIT_SUFFIX[unit]}"
