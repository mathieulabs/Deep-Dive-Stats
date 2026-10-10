# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Fixed-date period packed in one negative int (so it fits where a period int goes)."""

from datetime import date, timedelta

_BASE = 100_000_000
_EPOCH = date(1970, 1, 1)


def encode(start, end):
    """start/end are dates (both included)."""
    s = max(0, (start - _EPOCH).days)
    length = max(1, min(9999, (end - max(start, _EPOCH)).days + 1))
    return -(_BASE + s * 10000 + length)


def is_abs(value):
    return isinstance(value, int) and not isinstance(value, bool) and value <= -_BASE


def decode(value):
    """Return (start, end) dates, both included."""
    n = -int(value) - _BASE
    start = _EPOCH + timedelta(days=n // 10000)
    return start, start + timedelta(days=(n % 10000) - 1)
