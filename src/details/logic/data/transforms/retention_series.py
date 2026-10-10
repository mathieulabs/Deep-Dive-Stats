# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
RETENTION_SERIES_FIELDS = (
    ("all", "retention", "passed", "reviews"),
    ("young", "ret_young", "pass_young", "rev_young"),
    ("mature", "ret_mat", "pass_mat", "rev_mat"),
)
RETENTION_SERIES_KEYS = tuple(series_key for series_key, _, _, _ in RETENTION_SERIES_FIELDS)


def _retention_value(row, field_name, strict=False, default=None):
    if strict:
        return row[field_name]
    return row.get(field_name, default)


def build_retention_series(
    rows,
    strict_series=None,
    rate_defaults=None,
    count_default=None,
    count_defaults=None,
):
    strict_series = set(strict_series or ())
    rate_defaults = dict(rate_defaults or {})
    count_defaults = dict(count_defaults or {})

    result = {}
    for series_key, rate_key, passed_key, reviews_key in RETENTION_SERIES_FIELDS:
        strict = series_key in strict_series
        series_count_default = count_defaults.get(series_key, count_default)
        series_rate_default = rate_defaults.get(series_key)
        result[series_key] = [
            (
                row["pretty_date"],
                _retention_value(row, rate_key, strict=strict, default=series_rate_default),
                (
                    _retention_value(row, passed_key, strict=strict, default=series_count_default),
                    _retention_value(row, reviews_key, strict=strict, default=series_count_default),
                ),
            )
            for row in rows
        ]

    result["true"] = [_true_retention_point(row, strict_series, count_default, count_defaults) for row in rows]

    return result


def _true_retention_point(row, strict_series, count_default, count_defaults):
    """True retention: young and mature review answers together (learning cards left out)."""
    strict = "young" in strict_series or "mature" in strict_series
    passed = reviews = 0
    for series_key, _rate, passed_key, reviews_key in RETENTION_SERIES_FIELDS[1:]:
        default = count_defaults.get(series_key, count_default)
        passed += _retention_value(row, passed_key, strict=strict, default=default) or 0
        reviews += _retention_value(row, reviews_key, strict=strict, default=default) or 0
    rate = (passed / reviews * 100) if reviews > 0 else None
    return (row["pretty_date"], rate, (passed, reviews))
