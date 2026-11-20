# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ....const import Period
from ....i18n import tr, N_


def make_new_tab_definition():
    return {
        "title": tr("New Tab"),
        "range": Period.WEEK,
        "use_decimal": True,
        "hrs_unit": N_("hrs"),
        "min_unit": "min",
        "show_time": True,
        "show_reviews": True,
        "show_retention": True,
        "show_retention_young": True,
        "show_retention_mature": True,
        "show_avg_time": True,
        "show_counts": True,
        "show_streak": False,
        "show_active_days": True,
        "show_longest_streak": True,
        "show_buttons_dist": False,
        "show_forecast": True,
        "enabled": True,
    }


def set_tab_field(tabs_data, row, key, value):
    if row < 0 or row >= len(tabs_data or []):
        return False
    tabs_data[row][key] = value
    return True


def append_new_tab(tabs_data):
    tab = make_new_tab_definition()
    # the table's columns are the same for every span: the new one takes the others'
    from ..tabs.columns import FLAGS

    if tabs_data and isinstance(tabs_data[0], dict):
        for flag in list(FLAGS.values()) + ["show_counts"]:
            if flag in tabs_data[0]:
                tab[flag] = tabs_data[0][flag]
    tabs_data.append(tab)
    return len(tabs_data) - 1


def remove_tab(tabs_data, row, min_count=1):
    if row < 0 or row >= len(tabs_data or []):
        return False, "invalid_row", None
    if len(tabs_data) <= int(min_count):
        return False, "min_tabs", None
    removed_title = str(tabs_data[row].get("title", ""))
    del tabs_data[row]
    return True, "removed", removed_title

