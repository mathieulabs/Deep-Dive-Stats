# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""What a heatmap cell measures. The day entries already hold every field.

The metric is a string of keys joined by "+", for example "reviews", "time+failed"
or "young+relearn". Card types never overlap, so the types of a metric are summed
into one count. With several measures, each one is scaled on its own and the cell
shows their average.
"""

from .....i18n import N_

METRICS = (
    ("reviews", N_("Reviews")),
    ("time", N_("Time spent")),
    ("correct", N_("Correct answers")),
    ("failed", N_("Failed answers")),
    ("retention", N_("Retention %")),
    ("avg_time", N_("Average time per review")),
)
TYPE_METRICS = (
    ("new", N_("New cards")),
    ("young", N_("Young reviews")),
    ("mature", N_("Mature reviews")),
    ("relearn", N_("Relearning")),
    ("cram", N_("Filtered")),
)
METRIC_LABELS = dict(METRICS + TYPE_METRICS)
METRIC_KEYS = tuple(k for k, _ in METRICS)
TYPE_KEYS = tuple(k for k, _ in TYPE_METRICS)


def metric_parts(metric):
    """Selected keys of a metric string, or [] if it is not valid."""
    parts = str(metric or "").split("+")
    if parts and all(p in METRIC_LABELS for p in parts):
        return parts
    return []


def build_metric(parts):
    """Canonical metric string for a set of keys; "reviews" when empty."""
    chosen = [k for k in METRIC_KEYS + TYPE_KEYS if k in set(parts)]
    return "+".join(chosen) if chosen else "reviews"


