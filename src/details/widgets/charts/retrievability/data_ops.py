# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ...chart_utils.formatting import fmt_num_compact


def get_stats_text_impl(widget):
    if widget.total_cards > 0:
        avg = sum([k * v for k, v in widget.data_list]) / widget.total_cards
        return [
            f"Average retrievability: {fmt_num_compact(avg)}%",
            f"Estimated total knowledge: {int((avg/100) * widget.total_cards)} cards",
        ]
    return []


def get_tooltip_text_impl(widget, k, v):
    return f"Retrievability {k:.1f}%: {v} cards"


__all__ = [
    "get_stats_text_impl",
    "get_tooltip_text_impl",
]
