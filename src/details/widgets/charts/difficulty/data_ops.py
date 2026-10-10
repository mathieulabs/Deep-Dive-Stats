# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
def get_stats_text_impl(widget):
    if widget.total_cards > 0:
        run_sum = 0
        median = 0
        for k, v in widget.data_list:
            run_sum += v
            if run_sum >= widget.total_cards / 2:
                median = k
                break
        return [f"Median difficulty: {median}%"]
    return []


def get_tooltip_text_impl(widget, k, v):
    return f"Difficulty {k:.1f}%: {v} cards"
