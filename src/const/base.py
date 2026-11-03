# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import os
from ..i18n import N_

# Revlog type for a manual reschedule (Anki's own value when available).
try:
    from anki.consts import REVLOG_RESCHED
except Exception:
    REVLOG_RESCHED = 4

CURRENT_VERSION = '1.0.0'

# Anki's default hour at which a new study day starts.
DEFAULT_ROLLOVER_HOUR = 4

# Points at src/ (not the add-on root); assets/ lives inside it.
ADDON_PATH = os.path.dirname(os.path.dirname(__file__))
ASSETS_DIR = os.path.join(ADDON_PATH, "assets")
LOGO_PNG = os.path.join(ASSETS_DIR, "logo.png")

# Period values are saved in the config (tab ranges, widget time spans): don't renumber them.
class Period:
    TOTAL, WEEK, TWO_WEEKS, MONTH, YEAR, CUSTOM, TODAY, YESTERDAY = -1, 0, 1, 2, 3, 4, 5, 6
    LAST_YEAR = 7
    THREE_MONTHS = 8
    DAYS_IN = {WEEK: 7, TWO_WEEKS: 14, MONTH: 30, THREE_MONTHS: 90, YEAR: 365, CUSTOM: 1}
    LABEL = {
        WEEK: N_('Past Week'),
        TWO_WEEKS: N_('Past 2 Weeks'),
        MONTH: N_('Past Month'),
        THREE_MONTHS: N_('Past 3 Months'),
        YEAR: N_('Past Year'),
        LAST_YEAR: N_('Last Year'),
        TOTAL: N_('Total'),
        TODAY: N_('Today'),
        YESTERDAY: N_('Yesterday')
    }

LAST_YEAR = Period.LAST_YEAR



# Config keys for chart binning. They live here because config.py imports them from this module.
ADAPTIVE_CHART_BINNING = 'Adaptive_Chart_Binning'
CHART_BINNING_SCALE = 'Chart_Binning_Scale'
