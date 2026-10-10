# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""What a heatmap cell measures. The day entries already hold every field.

The metric is a string of keys joined by "+", for example "reviews", "time+failed"
or "young+relearn". Card types never overlap, so the types of a metric are summed
into one count. With several measures, each one is scaled on its own and the cell
shows their average.
"""

METRICS = (
    ("reviews", "Reviews"),
    ("time", "Time spent"),
    ("correct", "Correct answers"),
    ("failed", "Failed answers"),
    ("retention", "Retention %"),
    ("avg_time", "Average time per review"),
)
TYPE_METRICS = (
    ("new", "New cards"),
    ("young", "Young reviews"),
    ("mature", "Mature reviews"),
    ("relearn", "Relearning"),
    ("cram", "Filtered"),
)
METRIC_LABELS = dict(METRICS + TYPE_METRICS)
METRIC_KEYS = tuple(k for k, _ in METRICS)
TYPE_KEYS = tuple(k for k, _ in TYPE_METRICS)
_TYPE_FIELDS = {
    "new": "learn_count",
    "young": "young_count",
    "mature": "mature_count",
    "relearn": "relearn_count",
    "cram": "cram_count",
}


def metric_parts(metric):
    """Selected keys of a metric string, or [] if it is not valid."""
    parts = str(metric or "").split("+")
    if parts and all(p in METRIC_LABELS for p in parts):
        return parts
    return []


def normalize_metric(metric):
    return metric if metric_parts(metric) else "reviews"


def build_metric(parts):
    """Canonical metric string for a set of keys; "reviews" when empty."""
    chosen = [k for k in METRIC_KEYS + TYPE_KEYS if k in set(parts)]
    return "+".join(chosen) if chosen else "reviews"


def components(metric):
    """Measures of a metric: each stat, plus one "types" component for all chosen card types."""
    parts = metric_parts(metric) or ["reviews"]
    comps = [(p, None) for p in parts if p in METRIC_KEYS]
    types = tuple(p for p in parts if p in TYPE_KEYS)
    if types:
        comps.append(("types", types))
    return comps


def component_value(comp, entry):
    key, types = comp
    reviews = float(entry.get("reviews", 0) or 0)
    if key == "types":
        return float(sum(float(entry.get(_TYPE_FIELDS[t], 0) or 0) for t in types))
    if key == "time":
        return float(entry.get("time_ms", 0) or 0)
    if key == "correct":
        return float(entry.get("passed", 0) or 0)
    if key == "failed":
        return max(0.0, reviews - float(entry.get("passed", 0) or 0))
    if key == "retention":
        return float(entry.get("passed", 0) or 0) / reviews * 100.0 if reviews > 0 else 0.0
    if key == "avg_time":
        return float(entry.get("time_ms", 0) or 0) / reviews if reviews > 0 else 0.0
    return reviews


def component_label(comp):
    key, types = comp
    if key == "types":
        return " + ".join(METRIC_LABELS[t] for t in types)
    return METRIC_LABELS.get(key, key)


def metric_value(metric, entry, scales=None):
    """Value of one day entry for the given metric. Several measures are averaged
    after dividing each by its scale (`scales`, one per component)."""
    if not isinstance(entry, dict):
        return float(entry or 0)
    if "_v" in entry:  # interpolated frame of a data transition
        return float(entry["_v"] or 0)
    comps = components(metric)
    if len(comps) == 1:
        return component_value(comps[0], entry)
    scales = scales or ()
    total = 0.0
    for i, comp in enumerate(comps):
        scale = scales[i] if i < len(scales) and scales[i] else 1.0
        total += component_value(comp, entry) / scale
    return total / len(comps) * 100.0


def compute_scales(metric, entries):
    """Per-component scale (95th percentile of the non-zero values, like the colors)."""
    comps = components(metric)
    if len(comps) < 2:
        return ()
    scales = []
    for comp in comps:
        vals = sorted(v for v in (component_value(comp, e) for e in entries) if v > 0)
        if not vals:
            scales.append(1.0)
        elif len(vals) >= 20:
            scales.append(vals[min(len(vals) - 1, int(len(vals) * 0.95))])
        else:
            scales.append(vals[-1])
    return tuple(scales)


def entry_counts(widget, entry):
    """(value, future) of a day entry. Future reviews only exist for the Reviews metric."""
    metric = getattr(widget, "metric", "reviews")
    value = metric_value(metric, entry, getattr(widget, "_metric_scales", None))
    if metric != "reviews" or not isinstance(entry, dict):
        return value, 0.0
    return value, float(entry.get("future", 0) or 0)
