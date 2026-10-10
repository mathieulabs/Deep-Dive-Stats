# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ...chart_utils.formatting import fmt_num_compact


def normalize_rows_impl(rows):
    out = []
    for item in rows or []:
        if isinstance(item, dict):
            out.append({"pretty_date": str(item.get("pretty_date", "")), "count": float(item.get("count", 0) or 0)})
            continue
        if isinstance(item, (tuple, list)) and len(item) >= 2:
            out.append({"pretty_date": str(item[0]), "count": float(item[1] or 0)})
            continue
    return out


def stats_text_impl(widget):
    daily_counts = [float(item.get("count", 0) or 0) for item in (widget.data or [])]
    total = sum(daily_counts)
    if getattr(widget, "avg_on_active_days", False):
        non_zeros = [v for v in daily_counts if v > 0]
        avg = (sum(non_zeros) / len(non_zeros)) if non_zeros else 0.0
    else:
        avg = (sum(daily_counts) / len(daily_counts)) if daily_counts else 0.0
    return [f"Total: {fmt_num_compact(total)} added", f"Average: {fmt_num_compact(avg)}/day"]
