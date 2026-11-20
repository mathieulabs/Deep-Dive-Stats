# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from datetime import datetime, timedelta


DAY_MS = 86400000
TWO_DAYS_MS = 2 * DAY_MS
_TRANSITION_RESET_ATTRS = (
    ("_data_transition_active", False),
    ("_global_transition_mode", None),
    ("_transition_align_right", False),
    ("_transition_old_data", []),
    ("_transition_new_data", []),
    ("_transition_old_display_data", []),
    ("_transition_new_display_data", []),
    ("_transition_old_values", []),
    ("_transition_new_values", []),
)


def compute_transition_align_right(start_idx=None, end_idx=None, source_len=None, default=True):
    """Choose the visual anchor for a timespan morph based on the zoom window center."""
    try:
        total = int(source_len or 0)
        if total <= 0 or start_idx is None or end_idx is None:
            return bool(default)
        center_ratio = (float(start_idx) + float(end_idx)) / (2.0 * float(total))
        return center_ratio >= 0.5
    except Exception:
        return bool(default)


def resolve_adaptive_zoom_window(
    zoomed_slice,
    date_keys=("logical_date", "date"),
    date_formats=("%Y-%m-%d", "%Y/%m/%d"),
    max_span_ms=TWO_DAYS_MS,
):
    """Return parsed date bounds for adaptive zoom when the visible range is <= 2 days."""
    if not zoomed_slice or len(zoomed_slice) < 2:
        return None

    first_label = _get_date_label(zoomed_slice[0], date_keys)
    last_label = _get_date_label(zoomed_slice[-1], date_keys)
    if not first_label or not last_label:
        return None

    # Already sub-day data (e.g. TODAY/YESTERDAY hi-res bins).
    if " " in first_label or " " in last_label:
        return None

    first_dt = None
    last_dt = None
    for fmt in date_formats:
        try:
            first_dt = datetime.strptime(first_label, fmt)
            last_dt = datetime.strptime(last_label, fmt)
            break
        except ValueError:
            continue
    if first_dt is None or last_dt is None:
        return None

    span_ms = int((last_dt - first_dt).total_seconds() * 1000)
    if not (0 < span_ms <= int(max_span_ms)):
        return None

    return {
        "first_dt": first_dt,
        "last_dt": last_dt,
        "span_ms": span_ms,
        "first_label": first_label,
        "last_label": last_label,
    }


def widen_zoom_window(rows, start, end, factor=0.15, date_keys=("logical_date", "date")):
    """Window one wheel step wider than start:end, kept wider than the 2-day
    threshold so leaving the 10-minute view does not switch straight back to it.
    Returns (start, end); (0, len(rows)) means everything."""
    n = len(rows or [])
    if n <= 0:
        return 0, 0
    start = max(0, min(n - 1, int(start)))
    end = max(start + 1, min(n, int(end)))
    rng = end - start
    center = (start + end) / 2.0
    new_rng = max(rng + 1, int(rng * (1 + factor)))
    while True:
        new_rng = min(n, new_rng)
        s = int(round(center - new_rng / 2.0))
        s = max(0, min(s, n - new_rng))
        e = s + new_rng
        if new_rng >= n or resolve_adaptive_zoom_window(rows[s:e], date_keys=date_keys) is None:
            return s, e
        new_rng += 1


def build_adaptive_fetch_bounds(first_dt, last_dt, offset_seconds=0):
    """[start, end) in epoch ms of the Anki days first_dt .. last_dt (dates as naive local
    datetimes at midnight, offset_seconds = rollover hour). Added on the local time, so a
    day with a clock change keeps its 23 or 25 hours."""
    offset = timedelta(seconds=float(offset_seconds or 0))
    start_ms = int((first_dt + offset).timestamp() * 1000)
    end_ms = int((last_dt + offset + timedelta(days=1)).timestamp() * 1000)
    return start_ms, end_ms


def should_use_timespan_transition(
    meta,
    deck_policy="ignore",
    require_prev_commit=True,
    extra_trigger=False,
):
    if not require_prev_commit:
        return False

    deck_changed = bool((meta or {}).get("deck_changed", False))
    span_changed = bool((meta or {}).get("span_changed", False))
    total_bounds_changed = bool((meta or {}).get("total_bounds_changed", False))

    if str(deck_policy or "ignore") == "force":
        use_transition = deck_changed or span_changed
    elif str(deck_policy or "ignore") == "block":
        use_transition = (not deck_changed) and span_changed
    else:
        use_transition = span_changed

    if extra_trigger:
        if str(deck_policy or "ignore") == "block":
            use_transition = use_transition or (not deck_changed)
        else:
            use_transition = True

    return bool(use_transition or total_bounds_changed)


def timespan_transition_mode(meta, deck_policy="ignore", **kwargs):
    """Mode for a time chart's update: "window" when only the dates of a Total range changed
    (another deck, whose first review is on another day), "timespan" for another period,
    else None (the bars morph in place)."""
    if not should_use_timespan_transition(meta, deck_policy=deck_policy, **kwargs):
        return None
    m = meta or {}
    if m.get("total_bounds_changed") and not m.get("span_changed"):
        return "window"
    return "timespan"


def _row_day(row):
    if isinstance(row, (list, tuple)):
        return row[0] if row else None
    if isinstance(row, dict):
        for k in ("logical_date", "date", "pretty_date"):
            if row.get(k):
                return row.get(k)
    return None


def _empty_row(row):
    if isinstance(row, (list, tuple)):
        out = list(row)
        if len(out) >= 2:
            out[1] = 0
        return type(row)(out) if isinstance(row, tuple) else out
    if isinstance(row, dict):
        return {k: (0 if isinstance(v, (int, float)) and not isinstance(v, bool) else v) for k, v in row.items()}
    return 0


def rows_on_new_days(old_rows, new_rows):
    """The old rows put on the days of the new ones (a day the old data does not have counts
    0), or None when they share no day. A Total range of another deck starts on another
    day: morphed row by row, each bar would turn into another period (and another bin
    size); on the same days, each bar only changes its height, as on any deck change."""
    by_day = {}
    for r in old_rows or []:
        d = _row_day(r)
        if d is not None:
            by_day[str(d)] = r
    if not by_day:
        return None
    out, shared = [], 0
    for r in new_rows or []:
        old = by_day.get(str(_row_day(r)))
        if old is None:
            out.append(_empty_row(r))
        else:
            out.append(old)
            shared += 1
    return out if shared else None


def _get_date_label(item, date_keys):
    if not isinstance(item, dict):
        return ""
    for key in date_keys or ():
        value = str(item.get(key, "") or "").strip()
        if value:
            return value
    return ""


