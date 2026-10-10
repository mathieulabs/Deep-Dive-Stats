# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..common import get_review_button_colors


def refresh_data_colors_impl(widget):
    widget.colors = widget._pick_colors(get_review_button_colors(widget, as_qcolor=True))


def tooltip_text_impl(widget):
    total = sum(widget.counts)
    if total <= 0:
        return ""
    tips = []
    for i, count in enumerate(widget.counts):
        pct = (count / total) * 100
        tips.append(f"{widget.labels[i]}: {count} ({pct:.2f}%)")
    return " | ".join(tips)
