# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from .....i18n import num, tr, tr_n
def get_stats_text_impl(widget):
    if widget.total_cards > 0:
        run_sum = 0
        median = 0
        for k, v in widget.data_list:
            run_sum += v
            if run_sum >= widget.total_cards / 2:
                median = k
                break
        return [tr("Median difficulty: {value}%", value=median)]
    return []


def get_tooltip_text_impl(widget, k, v):
    return tr_n("Difficulty {value}%: {n} card", "Difficulty {value}%: {n} cards", v, value=num(f"{k:.1f}"))
