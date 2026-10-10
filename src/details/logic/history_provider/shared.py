# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from datetime import datetime, timedelta

from aqt import mw

from .. import Config, Period
from .. import (
    REVLOG_RESCHED,
    get_rollover_offset_ms, get_daystart_epoch_sql,
)
from ..data.core.time_utils import get_time_range_ms
from ..data.core.streaks import get_deck_streaks


