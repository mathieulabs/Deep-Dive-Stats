# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import inspect
from datetime import datetime
from .....logic.logger import log_swallowed


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
    start_ms = int((first_dt.timestamp() + float(offset_seconds or 0)) * 1000)
    end_ms = int((last_dt.timestamp() + float(offset_seconds or 0)) * 1000) + DAY_MS
    return start_ms, end_ms


def extract_series_date_bounds(series, date_keys=("pretty_date", "date", "logical_date")):
    if not series:
        return None

    first = _normalize_series_label(_get_series_label(series[0], date_keys), boundary="first")
    last = _normalize_series_label(_get_series_label(series[-1], date_keys), boundary="last")
    if not first and not last:
        return None
    return (first, last)


def get_timespan_transition_meta(
    prev_span_token,
    current_span_token,
    prev_deck_id=None,
    current_deck_id=None,
    old_series=None,
    new_series=None,
    total_span_active=False,
    date_keys=("pretty_date", "date", "logical_date"),
):
    old_bounds = extract_series_date_bounds(old_series, date_keys=date_keys)
    new_bounds = extract_series_date_bounds(new_series, date_keys=date_keys)
    deck_changed = False
    if (prev_deck_id is not None) and (current_deck_id is not None):
        deck_changed = prev_deck_id != current_deck_id

    return {
        "span_changed": prev_span_token != current_span_token,
        "deck_changed": deck_changed,
        "old_bounds": old_bounds,
        "new_bounds": new_bounds,
        "total_bounds_changed": bool(
            total_span_active and old_bounds and new_bounds and old_bounds != new_bounds
        ),
    }


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


def update_chart_for_transition(
    chart,
    data,
    adaptive_binning=None,
    transition_mode=None,
    transition_align_right=None,
    transition=False,
    transition_duration_ms=None,
):
    """Best-effort cross-chart update helper for activity/stacked/added/retention widgets."""
    if not (chart and hasattr(chart, "update_data")):
        return False
    from ....chart_utils import zoom_camera

    zoom_camera.touch(chart)

    kwargs = {}
    if adaptive_binning is not None and hasattr(chart, "adaptive_binning"):
        kwargs["adaptive_binning"] = adaptive_binning

    if hasattr(chart, "_full_retention_data"):
        kwargs["transition"] = bool(transition)
        if transition_duration_ms is not None:
            kwargs["transition_duration_ms"] = int(transition_duration_ms)
    else:
        kwargs["transition_mode"] = transition_mode
        if transition_align_right is not None:
            kwargs["transition_align_right"] = bool(transition_align_right)

    # Pass only the options this chart's update_data accepts.
    try:
        params = inspect.signature(chart.update_data).parameters
        if not any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
            kwargs = {k: v for k, v in kwargs.items() if k in params}
    except (TypeError, ValueError):
        pass
    chart.update_data(data, **kwargs)
    return True


def freeze_chart_transition_state(chart):
    if chart is None:
        return

    try:
        if hasattr(chart, "animation"):
            chart.animation.stop()
    except Exception:
        log_swallowed()

    if hasattr(chart, "set_progress"):
        chart.set_progress(1.0)
    else:
        setattr(chart, "_progress", 1.0)

    if hasattr(chart, "_initial_animation_done"):
        chart._initial_animation_done = True

    for attr, value in _TRANSITION_RESET_ATTRS:
        if hasattr(chart, attr):
            setattr(chart, attr, list(value) if isinstance(value, list) else value)

    if hasattr(chart, "update"):
        chart.update()


def _get_date_label(item, date_keys):
    if not isinstance(item, dict):
        return ""
    for key in date_keys or ():
        value = str(item.get(key, "") or "").strip()
        if value:
            return value
    return ""


def _get_series_label(item, date_keys):
    if isinstance(item, (tuple, list)):
        return str(item[0]) if item else ""
    if isinstance(item, dict):
        return _get_date_label(item, date_keys)
    return ""


def _normalize_series_label(label, boundary="first"):
    value = str(label or "").strip()
    if " - " in value:
        parts = value.split(" - ")
        if str(boundary or "first") == "last":
            value = parts[-1].strip()
        else:
            value = parts[0].strip()
    return value
