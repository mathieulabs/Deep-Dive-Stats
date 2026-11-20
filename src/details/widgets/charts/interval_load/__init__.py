# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Interval Load: how many reviews a day the cards of each interval bring.

A card with an interval of d days comes back about once every d days: it adds 1/d review
to each day (the sum of the bars is the daily load of the deck)."""

from ....logic.formatting import fmt_num_trim_zeros
from .....i18n import tr, tr_n


def to_load(data):
    """The review intervals data (distribution {interval: cards}) as load {interval: reviews/day}."""
    data = dict(data or {})
    dist = data.get("distribution") or {}
    load = {}
    for ivl, count in dist.items():
        try:
            d = int(ivl)
        except (TypeError, ValueError):
            continue
        if d >= 1 and count:
            load[d] = float(count) / d
    return {"distribution": load, "total": data.get("total", 0)}


