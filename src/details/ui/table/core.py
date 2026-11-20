# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ...logic.formatting import fmt_num, stats_precision, TREND_PRECISION
from ....i18n import num, tr


def get_trend_html(curr, prev, show_trends, bigger_is_better=True, color_good="#4CAF50", color_bad="#F44336", points=False):
    if not show_trends or prev <= 0:
        return ""
    # points=True: gap in percentage points (for values that are already a %, like retention)
    diff = (curr - prev) if points else ((curr - prev) / prev) * 100
    if abs(diff) < 0.1:
        return ""
    color = color_good if (diff > 0) == bigger_is_better else color_bad
    symbol = "▲" if diff > 0 else "▼"
    if points:
        points_text = tr("{value} pts", value=num(f"{abs(diff):.{TREND_PRECISION}f}"))
        return f' <small style="color:{color}; font-weight:bold;">{symbol}{points_text}</small>'
    return f' <small style="color:{color}; font-weight:bold;">{symbol}{num(f"{abs(diff):.{TREND_PRECISION}f}%")}</small>'


def get_dist_text(count, total, show_counts):
    if total > 0:
        v = count if show_counts else (count / total * 100)
        return fmt_num(v) if show_counts else num(f"{v:.{stats_precision()}f}%")
    return "0" if show_counts else num("0%")
