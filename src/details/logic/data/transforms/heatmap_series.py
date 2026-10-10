# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
HEATMAP_BASE_KEYS = (
    "reviews",
    "time_ms",
    "passed",
    "learn_count",
    "relearn_count",
    "young_count",
    "mature_count",
    "cram_count",
)


def build_heatmap_data(
    rows,
    date_key="logical_date",
    skip_zero_review_rows=False,
    include_future_key=False,
):
    heatmap_data = {}
    active_days_set = set()

    for row in rows or []:
        if not isinstance(row, dict):
            continue
        bucket_key = row.get(date_key)
        if not bucket_key:
            continue

        reviews = row.get("reviews", 0) or 0
        if skip_zero_review_rows and reviews <= 0:
            continue
        if reviews > 0:
            active_days_set.add(bucket_key)

        entry = heatmap_data.setdefault(
            bucket_key,
            make_heatmap_entry(include_future_key=include_future_key),
        )
        for key in HEATMAP_BASE_KEYS:
            entry[key] += row.get(key, 0) or 0

    return heatmap_data, active_days_set


def merge_heatmap_future_values(
    heatmap_data,
    future_reviews,
    mode="set",
    include_future_key=False,
):
    if not isinstance(heatmap_data, dict):
        heatmap_data = {}

    mode_str = str(mode or "set").strip().lower()
    for date_str, count in (future_reviews or {}).items():
        if not date_str:
            continue
        entry = heatmap_data.setdefault(
            date_str,
            make_heatmap_entry(include_future_key=include_future_key),
        )
        current = entry.get("future", 0) or 0
        next_value = count or 0

        if mode_str == "add":
            entry["future"] = current + next_value
        elif mode_str == "max":
            entry["future"] = max(current, next_value)
        else:
            entry["future"] = next_value

    return heatmap_data


def extract_heatmap_future_values(heatmap_data):
    future_reviews = {}
    for date_str, entry in (heatmap_data or {}).items():
        if not isinstance(entry, dict):
            continue
        future_val = entry.get("future", 0) or 0
        if future_val > 0:
            future_reviews[date_str] = future_val
    return future_reviews


def make_heatmap_entry(include_future_key=False):
    entry = {key: 0 for key in HEATMAP_BASE_KEYS}
    if include_future_key:
        entry["future"] = 0
    return entry
