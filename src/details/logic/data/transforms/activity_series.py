# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
BREAKDOWN_BASE_KEYS = ("mature", "young", "relearn", "learn", "cram")
REVIEW_TYPE_CHOICES = (
    ("learn", "Learning"),
    ("young", "Young"),
    ("mature", "Mature"),
    ("relearn", "Relearning"),
    ("cram", "Filtered / custom study"),
)
HIDDEN_TYPES_KEY = "hidden_review_types"


def normalize_hidden_types(value):
    """Review types hidden from the Activity chart, as a tuple of known keys (empty = all shown)."""
    if not isinstance(value, (list, tuple, set)):
        return ()
    known = {k for k, _ in REVIEW_TYPE_CHOICES}
    return tuple(k for k, _ in REVIEW_TYPE_CHOICES if k in set(value) and k in known)


def filter_activity_types(rows, hidden):
    """Copy of the day rows without the hidden review types.

    Counts and times of hidden types are zeroed and the "reviews" and "time_ms" totals are
    reduced by them, so the totals chart and the breakdown chart stay consistent.
    Works with both key styles ("mature" and "mature_count").
    """
    hidden = normalize_hidden_types(hidden)
    if not hidden:
        return rows
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            out.append(row)
            continue
        new = dict(row)
        removed_reviews = 0.0
        removed_time = 0.0
        exact_time = False
        for key in hidden:
            count_key = f"{key}_count" if f"{key}_count" in row else key
            if count_key in row:
                removed_reviews += float(row.get(count_key, 0) or 0.0)
            for k in {key, f"{key}_count"}:
                if k in new:
                    new[k] = 0
            time_key = f"{key}_time_ms"
            if row.get(time_key, None) is not None:
                exact_time = True
                removed_time += float(row.get(time_key, 0) or 0.0)
                new[time_key] = 0
        if "reviews" in row:
            old_reviews = float(row.get("reviews", 0) or 0.0)
            new["reviews"] = max(0.0, old_reviews - removed_reviews)
        else:
            old_reviews = 0.0
        if "time_ms" in row:
            old_time = float(row.get("time_ms", 0) or 0.0)
            if exact_time:
                new["time_ms"] = max(0.0, old_time - removed_time)
            elif old_reviews > 0:
                new["time_ms"] = old_time * (new.get("reviews", 0.0) / old_reviews)
        out.append(new)
    return out


def build_activity_series(rows, date_key="pretty_date", value_key="reviews", scale=1.0):
    factor = float(scale or 0.0) if scale is not None else 1.0
    if scale is None:
        factor = 1.0

    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        out.append(
            (
                row.get(date_key, ""),
                float(row.get(value_key, 0) or 0.0) * factor,
            )
        )
    return out


def build_activity_series_from_breakdown(
    rows,
    date_key="pretty_date",
    count_key_style="plain",
    breakdown_keys=BREAKDOWN_BASE_KEYS,
):
    out = []
    resolved_keys = [_resolve_count_key(key, count_key_style) for key in (breakdown_keys or BREAKDOWN_BASE_KEYS)]
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        total = sum(float(row.get(key, 0) or 0.0) for key in resolved_keys)
        out.append((row.get(date_key, ""), total))
    return out


def build_breakdown_rows(
    rows,
    date_key="pretty_date",
    count_key_style="plain",
    include_time_fields=True,
    include_totals=True,
    breakdown_keys=BREAKDOWN_BASE_KEYS,
):
    out = []
    for row in rows or []:
        src = dict(row or {})
        item = {date_key: src.get(date_key, "")}
        for key in breakdown_keys or BREAKDOWN_BASE_KEYS:
            item[_resolve_count_key(key, count_key_style)] = src.get(f"{key}_count", 0)
            if include_time_fields:
                item[f"{key}_time_ms"] = src.get(f"{key}_time_ms", 0)
        if include_totals:
            item["time_ms"] = src.get("time_ms", 0)
            item["reviews"] = src.get("reviews", 0)
        out.append(item)
    return out


def attach_breakdown_totals(
    rows,
    raw_rows,
    date_key="pretty_date",
    total_keys=("time_ms", "reviews"),
):
    out_rows = [dict(row or {}) for row in (rows or [])]
    raw = list(raw_rows or [])
    if not out_rows:
        return out_rows

    if len(out_rows) == len(raw):
        for idx, row in enumerate(out_rows):
            src = raw[idx] or {}
            for key in total_keys or ():
                row[key] = float(src.get(key, 0) or 0.0)
        return out_rows

    by_label = {}
    for src in raw:
        label = str((src or {}).get(date_key, "") or "").strip()
        if label and label not in by_label:
            by_label[label] = src

    for row in out_rows:
        label = str(row.get(date_key, "") or "").strip()
        src = by_label.get(label) or {}
        for key in total_keys or ():
            row[key] = float(src.get(key, 0) or 0.0)
    return out_rows


def convert_breakdown_metric_rows(
    rows,
    mode,
    date_key="pretty_date",
    count_key_style="plain",
    breakdown_keys=BREAKDOWN_BASE_KEYS,
    preserve_source_fields=False,
):
    mode_str = str(mode or "reviews").strip().lower()
    if mode_str != "time":
        return [dict(row or {}) for row in (rows or [])]

    resolved_keys = [_resolve_count_key(key, count_key_style) for key in (breakdown_keys or BREAKDOWN_BASE_KEYS)]
    out = []
    for row in rows or []:
        src = dict(row or {})
        reviews = float(src.get("reviews", 0) or 0.0)
        time_ms = float(src.get("time_ms", 0) or 0.0)
        total_minutes = max(0.0, time_ms / 60000.0)
        dst = dict(src) if preserve_source_fields else {date_key: src.get(date_key, "")}

        has_exact = any(src.get(f"{key}_time_ms", None) is not None for key in (breakdown_keys or BREAKDOWN_BASE_KEYS))
        if has_exact:
            for base_key, resolved_key in zip((breakdown_keys or BREAKDOWN_BASE_KEYS), resolved_keys):
                dst[resolved_key] = max(0.0, float(src.get(f"{base_key}_time_ms", 0) or 0.0) / 60000.0)
        elif reviews > 0.0 and total_minutes > 0.0:
            ratio = total_minutes / reviews
            for resolved_key in resolved_keys:
                dst[resolved_key] = max(0.0, float(src.get(resolved_key, 0) or 0.0) * ratio)
        else:
            for resolved_key in resolved_keys:
                dst[resolved_key] = 0.0

        dst["reviews"] = reviews
        dst["time_ms"] = time_ms
        out.append(dst)
    return out


def _resolve_count_key(base_key, count_key_style):
    if str(count_key_style or "plain").strip().lower() == "count":
        return f"{base_key}_count"
    return base_key
