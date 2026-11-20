# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Due Today by Hour: the learning cards due today (Anki's intraday learning queue), by the
hour they come due, learning and relearning stacked."""

from ..daily_metrics import DailyMetric
from .....i18n import N_, tr


def _series(cfg):
    from ....ui import Config, get_color

    def color(key):
        return get_color(cfg.config, key, "details")

    return [
        {"key": "relearn", "label": tr("Relearning"), "color": color(Config.COLOR_RELEARN), "color_key": Config.COLOR_RELEARN},
        {"key": "learn", "label": tr("Learning"), "color": color(Config.COLOR_LEARN), "color_key": Config.COLOR_LEARN},
    ]


def _rows(payload):
    if isinstance(payload, dict):
        return list(payload.get("rows") or [])
    return list(payload or [])


METRIC = DailyMetric("due_today", N_("Due Today by Hour"), N_("Load and due"), _series, _rows,
                     unit="cards", cumulative=True)


def fetch(cfg, deck_id=None, is_deleted=False):
    from ....logic.metrics.future_due import due_today_by_hour

    return due_today_by_hour(cfg, deck_id, is_deleted)


