# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt import mw

from ... import Config, ConfigManager
from .loader import load_stats_data


def fetch_stats_for_range(
    range_type,
    week_start,
    custom_days=7,
    custom_type="relative",
    start_date="",
    end_date="",
    pin_top=True,
    spark_precision=False,
):
    """Global-config helper used by interaction flows for one range snapshot."""
    cfg_mgr = ConfigManager(mw)
    excluded_dids = cfg_mgr.config.get(Config.EXCLUDED_DECKS, [])
    show_trends = cfg_mgr.config.get(Config.SHOW_TRENDS, False)

    return load_stats_data(
        range_type=range_type,
        excluded_dids=excluded_dids,
        spark_precision=spark_precision,
        show_trends=show_trends,
        week_start=week_start,
        custom_days=custom_days,
        custom_type=custom_type,
        start_date_str=start_date,
        end_date_str=end_date,
    )

