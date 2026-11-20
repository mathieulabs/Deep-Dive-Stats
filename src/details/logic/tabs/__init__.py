# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import copy
from .. import Config, LAST_YEAR, Period
from ....i18n import N_

DEFAULT_DETAILS_TABS = [
    {"title": N_("Total"), "range": Period.TOTAL, "use_decimal": True, "hrs_unit": N_("hrs"), "min_unit": "min", "show_time": True, "show_reviews": True, "show_retention": True, "show_retention_young": True, "show_retention_mature": True, "show_avg_time": True, "show_counts": True, "show_streak": True, "show_longest_streak": True, "show_buttons_dist": True, "row_height": 30, "show_active_days": True, "show_forecast": True},
    {"title": N_("Today"), "range": Period.TODAY, "use_decimal": True, "hrs_unit": N_("hrs"), "min_unit": "min", "show_time": True, "show_reviews": True, "show_retention": True, "show_retention_young": True, "show_retention_mature": True, "show_avg_time": True, "show_counts": True, "show_streak": True, "show_longest_streak": True, "show_buttons_dist": True, "row_height": 30, "show_active_days": True, "show_forecast": True},
    {"title": N_("Yesterday"), "range": Period.YESTERDAY, "use_decimal": True, "hrs_unit": N_("hrs"), "min_unit": "min", "show_time": True, "show_reviews": True, "show_retention": True, "show_retention_young": True, "show_retention_mature": True, "show_avg_time": True, "show_counts": True, "show_streak": True, "show_longest_streak": True, "show_buttons_dist": True, "row_height": 30, "show_active_days": True, "show_forecast": True},
    {"title": N_("Past Week"), "range": Period.WEEK, "use_decimal": True, "hrs_unit": N_("hrs"), "min_unit": "min", "show_time": True, "show_reviews": True, "show_retention": True, "show_retention_young": True, "show_retention_mature": True, "show_avg_time": True, "show_counts": True, "show_streak": True, "show_longest_streak": True, "show_buttons_dist": True, "row_height": 30, "show_active_days": True, "show_forecast": True},
    {"title": N_("Past 2 Weeks"), "range": Period.TWO_WEEKS, "use_decimal": True, "hrs_unit": N_("hrs"), "min_unit": "min", "show_time": True, "show_reviews": True, "show_retention": True, "show_retention_young": True, "show_retention_mature": True, "show_avg_time": True, "show_counts": True, "show_streak": True, "show_longest_streak": True, "show_buttons_dist": True, "row_height": 30, "show_active_days": True, "show_forecast": True},
    {"title": N_("Past Month"), "range": Period.MONTH, "use_decimal": True, "hrs_unit": N_("hrs"), "min_unit": "min", "show_time": True, "show_reviews": True, "show_retention": True, "show_retention_young": True, "show_retention_mature": True, "show_avg_time": True, "show_counts": True, "show_streak": True, "show_longest_streak": True, "show_buttons_dist": True, "row_height": 30, "show_active_days": True, "show_forecast": True},
    {"title": N_("Past Year"), "range": Period.YEAR, "use_decimal": True, "hrs_unit": N_("hrs"), "min_unit": "min", "show_time": True, "show_reviews": True, "show_retention": True, "show_retention_young": True, "show_retention_mature": True, "show_avg_time": True, "show_counts": True, "show_streak": True, "show_longest_streak": True, "show_buttons_dist": True, "row_height": 30, "show_active_days": True, "show_forecast": True},
    {"title": N_("Last Year"), "range": LAST_YEAR, "use_decimal": True, "hrs_unit": N_("hrs"), "min_unit": "min", "show_time": True, "show_reviews": True, "show_retention": True, "show_retention_young": True, "show_retention_mature": True, "show_avg_time": True, "show_counts": True, "show_streak": True, "show_longest_streak": True, "show_buttons_dist": True, "row_height": 30, "show_active_days": True, "show_forecast": True},
]


def get_tabs_config(addon_config):
    return addon_config.config.get(Config.DETAILS_TABS_DATA, copy.deepcopy(DEFAULT_DETAILS_TABS))


def get_active_tabs_config(addon_config):
    """Enabled time spans, in the order of the tabs of the Details window."""
    return [t for t in get_tabs_config(addon_config) if t.get("enabled", True)]


def save_tabs_config(addon_config, tabs_data):
    addon_config.config[Config.DETAILS_TABS_DATA] = tabs_data
    addon_config.write_config()
