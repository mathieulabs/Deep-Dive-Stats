# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ...data.transforms.activity_series import build_activity_series, build_breakdown_rows
from ...data.transforms.heatmap_series import (
    build_heatmap_data,
    merge_heatmap_future_values,
)
from ...data.transforms.retention_series import build_retention_series


def build_processed_heatmap(reviews_history, future_reviews):
    processed_heatmap, active_days_set = build_heatmap_data(
        reviews_history,
        skip_zero_review_rows=True,
        include_future_key=True,
    )
    merge_heatmap_future_values(
        processed_heatmap,
        future_reviews,
        mode="add",
        include_future_key=True,
    )
    return processed_heatmap, active_days_set


def build_activity_and_retention_data(reviews_history):
    oldest_first = reviews_history[::-1]

    activity_data = build_activity_series(oldest_first)
    activity_breakdown = build_breakdown_rows(oldest_first, count_key_style="plain")

    retention_data = build_retention_series(oldest_first, strict_series=("all",))

    return activity_data, activity_breakdown, retention_data
