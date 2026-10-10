# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ...logic import Period


FUTURE_DUE_RANGES = (Period.MONTH, Period.THREE_MONTHS, Period.YEAR, Period.TOTAL)
FUTURE_DUE_LABELS_SHORT = ("1m", "3m", "1y", "all")
FUTURE_DUE_LABELS_LONG = ("1 month", "3 months", "1 year", "all")

# The four radio buttons can be changed per chart. Each button is a number of days
# (-1 means "all"). Spans for the usual values stay the existing Period constants;
# other values are packed as FD_DAYS_BASE + days (the pinned span normalizer keeps
# 1000..9999 as is).
FD_DAYS_BASE = 1000
FUTURE_DUE_DEFAULT_DAYS = (31, 90, 365, -1)
FUTURE_DUE_DAY_CHOICES = (
    (7, "1 week", "1w"),
    (14, "2 weeks", "2w"),
    (31, "1 month", "1m"),
    (60, "2 months", "2m"),
    (90, "3 months", "3m"),
    (180, "6 months", "6m"),
    (365, "1 year", "1y"),
    (730, "2 years", "2y"),
    (1825, "5 years", "5y"),
    (-1, "all", "all"),
)
_DAYS_TO_SPAN = {31: Period.MONTH, 90: Period.THREE_MONTHS, 365: Period.YEAR, -1: Period.TOTAL}
_PRESET_DAYS = {d for d, _l, _s in FUTURE_DUE_DAY_CHOICES}
MAX_CUSTOM_DAYS = 8999


def is_valid_future_due_days(days):
    return days in _PRESET_DAYS or (isinstance(days, int) and 1 <= days <= MAX_CUSTOM_DAYS)


def future_due_days_to_span(days):
    return _DAYS_TO_SPAN.get(days, FD_DAYS_BASE + int(days))


def future_due_span_max_days(span):
    """Largest day shown for a span, or None when it follows the data (all)."""
    if isinstance(span, int) and FD_DAYS_BASE <= span <= 9999:
        return span - FD_DAYS_BASE
    return {Period.MONTH: 31, Period.THREE_MONTHS: 90, Period.YEAR: 365}.get(span)


def normalize_future_due_days(days_list):
    """Four valid, ordered day values (all last); anything unusable gives the defaults."""
    try:
        values = [int(d) for d in (days_list or [])]
    except Exception:
        return FUTURE_DUE_DEFAULT_DAYS
    if len(values) != 4 or any(not is_valid_future_due_days(v) for v in values):
        return FUTURE_DUE_DEFAULT_DAYS
    return tuple(sorted(set(values), key=lambda d: (d == -1, d))) if len(set(values)) == 4 else FUTURE_DUE_DEFAULT_DAYS


def resolve_future_due_ranges(days_list=None):
    """Return (ranges, short_labels, long_labels) for the four radio buttons."""
    days = normalize_future_due_days(days_list)
    short = {d: s for d, _l, s in FUTURE_DUE_DAY_CHOICES}
    long_ = {d: l for d, l, _s in FUTURE_DUE_DAY_CHOICES}
    return (
        tuple(future_due_days_to_span(d) for d in days),
        tuple(short.get(d, f"{d}d") for d in days),
        tuple(long_.get(d, f"{d} days") for d in days),
    )


def clamp_future_due_idx(idx, default_idx=0, count=len(FUTURE_DUE_RANGES)):
    try:
        resolved = int(idx)
    except Exception:
        resolved = int(default_idx)

    if resolved < 0 or resolved >= count:
        return int(default_idx)
    return resolved


def get_future_due_range(idx, default_idx=0, ranges=FUTURE_DUE_RANGES):
    return ranges[clamp_future_due_idx(idx, default_idx=default_idx, count=len(ranges))]


def resolve_future_due_choice(idx=None, fallback_range=None, default_idx=0, ranges=FUTURE_DUE_RANGES):
    if idx is not None:
        resolved_idx = clamp_future_due_idx(idx, default_idx=default_idx, count=len(ranges))
        return resolved_idx, ranges[resolved_idx], "saved"

    if fallback_range in ranges:
        resolved_idx = ranges.index(fallback_range)
        return resolved_idx, fallback_range, "fallback_range"

    resolved_idx = clamp_future_due_idx(default_idx, default_idx=default_idx, count=len(ranges))
    return resolved_idx, ranges[resolved_idx], "default"
