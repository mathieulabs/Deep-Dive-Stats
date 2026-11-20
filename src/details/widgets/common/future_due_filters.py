# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ...logic import Period
from ....i18n import tr, tr_n, N_, tr_name


FUTURE_DUE_RANGES = (Period.MONTH, Period.THREE_MONTHS, Period.YEAR, Period.TOTAL)
FUTURE_DUE_LABELS_SHORT = (N_("1m"), N_("3m"), N_("1y"), N_("all"))
FUTURE_DUE_LABELS_LONG = (N_("1 month"), N_("3 months"), N_("1 year"), N_("all"))

# The four radio buttons can be changed per chart. Each button is a number of days
# (-1 means "all"). Spans for the usual values stay the existing Period constants;
# other values are packed as FD_DAYS_BASE + days (the pinned span normalizer keeps
# 1000..9999 as is).
FD_DAYS_BASE = 1000
FUTURE_DUE_DEFAULT_DAYS = (31, 90, 365, -1)
FUTURE_DUE_DAY_CHOICES = (
    (7, N_("1 week"), N_("1w")),
    (14, N_("2 weeks"), N_("2w")),
    (31, N_("1 month"), N_("1m")),
    (60, N_("2 months"), N_("2m")),
    (90, N_("3 months"), N_("3m")),
    (180, N_("6 months"), N_("6m")),
    (365, N_("1 year"), N_("1y")),
    (730, N_("2 years"), N_("2y")),
    (1825, N_("5 years"), N_("5y")),
    (-1, N_("all"), N_("all")),
)
_DAYS_TO_SPAN = {31: Period.MONTH, 90: Period.THREE_MONTHS, 365: Period.YEAR, -1: Period.TOTAL}
_PRESET_DAYS = {d for d, _l, _s in FUTURE_DUE_DAY_CHOICES}
MAX_CUSTOM_DAYS = 8999


def is_valid_future_due_days(days):
    return days in _PRESET_DAYS or (isinstance(days, int) and 1 <= days <= MAX_CUSTOM_DAYS)


def future_due_days_to_span(days):
    return _DAYS_TO_SPAN.get(days, FD_DAYS_BASE + int(days))


MIN_BUTTONS, MAX_BUTTONS = 2, 8  # how many range buttons a chart can have (folded into a menu when narrow)


def normalize_future_due_days(days_list):
    """2 to 8 valid, distinct, ordered day values (all last); anything unusable gives the defaults."""
    try:
        values = [int(d) for d in (days_list or [])]
    except Exception:
        return FUTURE_DUE_DEFAULT_DAYS
    if not MIN_BUTTONS <= len(values) <= MAX_BUTTONS or any(not is_valid_future_due_days(v) for v in values):
        return FUTURE_DUE_DEFAULT_DAYS
    if len(set(values)) != len(values):
        return FUTURE_DUE_DEFAULT_DAYS
    return tuple(sorted(values, key=lambda d: (d == -1, d)))


def resolve_future_due_ranges(days_list=None):
    """Return (ranges, short_labels, long_labels) for the radio buttons."""
    days = normalize_future_due_days(days_list)
    short = {d: s for d, _l, s in FUTURE_DUE_DAY_CHOICES}
    long_ = {d: l for d, l, _s in FUTURE_DUE_DAY_CHOICES}
    return (
        tuple(future_due_days_to_span(d) for d in days),
        tuple(tr_name(short[d]) if d in short else tr("{n}d", n=d) for d in days),
        tuple(tr_name(long_[d]) if d in long_ else tr_n("{n} day", "{n} days", d) for d in days),
    )


def clamp_future_due_idx(idx, default_idx=0, count=len(FUTURE_DUE_RANGES)):
    try:
        resolved = int(idx)
    except Exception:
        resolved = int(default_idx)

    if resolved < 0 or resolved >= count:
        return int(default_idx)
    return resolved


def resolve_future_due_choice(idx=None, fallback_range=None, default_idx=0, ranges=FUTURE_DUE_RANGES):
    if idx is not None:
        resolved_idx = clamp_future_due_idx(idx, default_idx=default_idx, count=len(ranges))
        return resolved_idx, ranges[resolved_idx], "saved"

    if fallback_range in ranges:
        resolved_idx = ranges.index(fallback_range)
        return resolved_idx, fallback_range, "fallback_range"

    resolved_idx = clamp_future_due_idx(default_idx, default_idx=default_idx, count=len(ranges))
    return resolved_idx, ranges[resolved_idx], "default"
