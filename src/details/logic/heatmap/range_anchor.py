# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Keep the Deep Dive heatmap on the selected period (and on the zoomed range)."""
from datetime import datetime, timedelta


def range_last_day(history_range, custom_days=7, custom_type="relative", start_date_str="", end_date_str=""):
    """Last Anki day covered by a Deep Dive period (e.g. Dec 31 for 'Last year')."""
    try:
        from .. import rollover_hour
        from ..data.core.time_utils import get_time_range_ms

        _s, end_ms, _ps, _pe = get_time_range_ms(
            int(history_range),
            0,
            custom_days=custom_days,
            custom_type=custom_type,
            start_date_str=start_date_str,
            end_date_str=end_date_str,
        )
        return (datetime.fromtimestamp((int(end_ms) - 1) / 1000.0) - timedelta(hours=rollover_hour())).date()
    except Exception:
        return None


