# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ... import LAST_YEAR, Period
from .....i18n import N_


RANGE_OPTIONS = [
    (N_("Today"), Period.TODAY),
    (N_("Yesterday"), Period.YESTERDAY),
    (N_("Total"), Period.TOTAL),
    (N_("Past Week"), Period.WEEK),
    (N_("Past 2 Weeks"), Period.TWO_WEEKS),
    (N_("Past Month"), Period.MONTH),
    (N_("Past Year"), Period.YEAR),
    (N_("Last Year"), LAST_YEAR),
    (N_("Custom"), Period.CUSTOM),
]

