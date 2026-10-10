# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ... import LAST_YEAR, Period


RANGE_OPTIONS = [
    ("Today", Period.TODAY),
    ("Yesterday", Period.YESTERDAY),
    ("Total", Period.TOTAL),
    ("Past Week", Period.WEEK),
    ("Past 2 Weeks", Period.TWO_WEEKS),
    ("Past Month", Period.MONTH),
    ("Past Year", Period.YEAR),
    ("Last Year", LAST_YEAR),
    ("Custom", Period.CUSTOM),
]

