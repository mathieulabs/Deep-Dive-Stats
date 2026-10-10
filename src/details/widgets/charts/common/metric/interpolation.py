# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
def pad_transition_values(old_rows, new_rows, *, to_value, align_right=False):
    n = max(len(old_rows), len(new_rows))
    if n <= 0:
        return [], [], 0

    old_vals = [float(to_value(v) or 0.0) for v in old_rows]
    new_vals = [float(to_value(v) or 0.0) for v in new_rows]

    if len(old_vals) < n:
        pad = [0.0] * (n - len(old_vals))
        old_vals = (pad + old_vals) if align_right else (old_vals + pad)
    if len(new_vals) < n:
        pad = [0.0] * (n - len(new_vals))
        new_vals = (pad + new_vals) if align_right else (new_vals + pad)

    return old_vals, new_vals, n


def pad_transition_rows(old_rows, new_rows, *, align_right=False, pad_factory=dict):
    n = max(len(old_rows), len(new_rows))
    if n <= 0:
        return [], [], 0

    old_rows = list(old_rows or [])
    new_rows = list(new_rows or [])

    if len(old_rows) < n:
        pad = [pad_factory() for _ in range(n - len(old_rows))]
        old_rows = (pad + old_rows) if align_right else (old_rows + pad)
    if len(new_rows) < n:
        pad = [pad_factory() for _ in range(n - len(new_rows))]
        new_rows = (pad + new_rows) if align_right else (new_rows + pad)

    return old_rows, new_rows, n


def build_cumulative_values(values):
    out = []
    run_sum = 0.0
    for value in values:
        run_sum += float(value or 0.0)
        out.append(run_sum)
    return out


def safe_positive_max(values, default=1.0):
    max_val = max(values) if values else 0.0
    if max_val <= 0.0:
        return float(default)
    return float(max_val)
