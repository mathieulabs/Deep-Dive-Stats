# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ...chart_utils.formatting import fmt_num_compact
from .....i18n import num, tr, tr_n


def get_stats_text_impl(widget):
    if widget.total_cards > 0:
        avg = sum([k * v for k, v in widget.data_list]) / widget.total_cards
        return [
            tr("Average retrievability: {value}%", value=fmt_num_compact(avg)),
            tr_n("Estimated total knowledge: {n} card", "Estimated total knowledge: {n} cards",
                 int((avg / 100) * widget.total_cards)),
        ]
    return []


def get_tooltip_text_impl(widget, k, v):
    return tr_n("Retrievability {value}%: {n} card", "Retrievability {value}%: {n} cards", v, value=num(f"{k:.1f}"))


__all__ = [
    "get_stats_text_impl",
    "get_tooltip_text_impl",
]
