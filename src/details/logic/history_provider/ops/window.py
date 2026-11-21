# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from datetime import datetime, timedelta

from ... import Config, Period
from ...data.core.time_utils import get_time_range_ms


def fetch_window(addon_config, range_type, override_start_ms, override_end_ms, override_bin_ms,
                 custom_days, custom_type, start_date_str, end_date_str, first_ms):
    """(start_ms, end_ms, is_hourly, ms_per_bin) of a history fetch. Total starts at first_ms() (the first card or
    review of the decks), a year back when there is none; under two days the bins are 10 minutes, else days."""
    if override_start_ms is not None and override_end_ms is not None:
        start_ms, end_ms = override_start_ms, override_end_ms
    else:
        week_start = addon_config.config.get(Config.WEEK_START, 0)
        start_ms, end_ms, _, _ = get_time_range_ms(
            range_type,
            week_start=week_start,
            custom_days=custom_days,
            custom_type=custom_type,
            start_date_str=start_date_str,
            end_date_str=end_date_str,
        )
        if range_type == Period.TOTAL:
            start_ms = first_ms() or int((datetime.now() - timedelta(days=365)).timestamp() * 1000)

    if override_bin_ms is not None:
        ms_per_bin = override_bin_ms
        is_hourly = ms_per_bin < 86400000
    else:
        is_hourly = range_type in [Period.TODAY, Period.YESTERDAY] or (end_ms - start_ms <= 2 * 86400 * 1000)
        ms_per_bin = 600000 if is_hourly else 86400000
    return start_ms, end_ms, is_hourly, ms_per_bin
