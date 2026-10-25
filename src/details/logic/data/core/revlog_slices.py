# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Read the revlog in slices, so the add-on never holds the collection for long.

Anki lets one query at a time use the collection. A query over a large revlog holds it
for seconds, and any card answered or button clicked meanwhile waits ("Processing...").
In slices of 25,000 reviews, Anki gets the collection back between two of them.
"""
import time

from aqt import mw

SLICE_ROWS = 25000
_MS_IDS = 1000000000000  # review ids below this are in seconds (very old collections)


def _ids_in_ms():
    """True when every review id is in milliseconds (ids in seconds only exist in very old
    collections, and their order does not follow the review time)."""
    try:
        first = mw.col.db.scalar("SELECT id FROM revlog ORDER BY id LIMIT 1")
    except Exception:
        return False
    return first is not None and int(first) >= _MS_IDS


_BOUNDS_CACHE = {}  # (collection, rows) -> (newest id, slice upper bounds, reviews added since)


def _slice_bounds(rows):
    """Upper revlog ids of the slices, oldest first. Kept until the revlog grows by a slice:
    any list of bounds splits the revlog correctly (only the slice sizes drift), so this
    is never wrong, and saves walking the revlog before every query."""
    col = mw.col
    newest = int(col.db.scalar("SELECT id FROM revlog ORDER BY id DESC LIMIT 1") or 0)
    key = (id(col), rows)
    cached = _BOUNDS_CACHE.get(key)
    if cached is not None and 0 <= newest - cached[0] and cached[2] < rows:
        if newest != cached[0]:
            grown = int(col.db.scalar(f"SELECT count() FROM revlog WHERE id > {cached[0]}") or 0)
            _BOUNDS_CACHE[key] = cached = (newest, cached[1], cached[2] + grown)
            if cached[2] >= rows:
                cached = None
        if cached is not None:
            return cached[1]
    bounds = []
    lo = None
    while True:
        after = "" if lo is None else f"WHERE id > {lo}"
        hi = col.db.scalar(f"SELECT id FROM revlog {after} ORDER BY id LIMIT 1 OFFSET {rows - 1}")
        if hi is None:
            break
        bounds.append(int(hi))
        lo = hi
    _BOUNDS_CACHE.clear()  # one collection at a time
    _BOUNDS_CACHE[key] = (newest, bounds, 0)
    return bounds


def revlog_slices(rows=SLICE_ROWS, start_id=None):
    """SQL conditions on revlog.id that split the revlog (from start_id on) into slices of
    about `rows` reviews."""
    out = []
    lo = None if not start_id else int(start_id) - 1
    for hi in _slice_bounds(rows):
        if lo is not None and hi <= lo:
            continue
        lower = "" if lo is None else f"AND revlog.id > {lo}"
        out.append(f"{lower} AND revlog.id <= {hi}")
        lo = hi
    out.append("" if lo is None else f"AND revlog.id > {lo}")
    return out


def sliced_all(make_query, slices, key_len):
    """Run make_query(slice) for each slice and add up the rows that share a group key
    (the first key_len columns); every other column must be a sum or a count."""
    if len(slices) == 1:
        return mw.col.db.all(make_query(slices[0]))
    merged = {}
    for i, part in enumerate(slices):
        if i:
            time.sleep(0.001)  # let a waiting review take the collection
        for row in mw.col.db.all(make_query(part)):
            key = tuple(row[:key_len])
            acc = merged.get(key)
            if acc is None:
                merged[key] = list(row)
            else:
                for j in range(key_len, len(row)):
                    acc[j] = (acc[j] or 0) + (row[j] or 0)
    return list(merged.values())


def scan_slices(start_ms=0, end_ms=None):
    """Slices for a scan of the reviews in [start_ms, end_ms): the slices before start_ms are
    skipped. The query keeps its own time conditions; it must not add another revlog.id
    bound, or SQLite may use that one for the scan and read past the end of each slice."""
    start_id = int(start_ms) if start_ms and int(start_ms) > 0 and _ids_in_ms() else None
    return revlog_slices(start_id=start_id)
