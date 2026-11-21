# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Collection review-year span helpers for the heatmap "Years" view."""
from datetime import datetime

_REVIEW_YEARS_CACHE = {}  # id(collection): (time, first year, last year)
_REVIEW_YEARS_TTL = 300.0


def collection_review_years():
    """Calendar years the open collection's reviews span (first to last review; 0 if none)."""
    try:
        import time
        from aqt import mw

        col = mw.col
        key = id(col)
        now = time.monotonic()
        cached = _REVIEW_YEARS_CACHE.get(key)
        if cached is None or now - cached[0] > _REVIEW_YEARS_TTL:
            lo, hi = col.db.first("select min(id), max(id) from revlog") or (None, None)
            if not lo or not hi:
                cached = (now, 0, 0)
            else:
                cached = (now, datetime.fromtimestamp(lo / 1000.0).year, datetime.fromtimestamp(hi / 1000.0).year)
            _REVIEW_YEARS_CACHE.clear()
            _REVIEW_YEARS_CACHE[key] = cached
        _t, first, last = cached
        if not first:
            return 0
        return last - first + 1
    except Exception:
        return 0


