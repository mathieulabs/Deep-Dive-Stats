# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The deck table's columns: every one that can be shown, and the ones shown (one list for every time span).

The columns were chosen per time span (show_* in each span); the first span's choice is taken over the first time
the list is read. The old show_* of every span are still written when the list changes, so anything still reading
them shows the same columns."""

from .. import Config
from ....i18n import N_

# (key, label, group, old per-span flag or None). Shown in this order. The labels of the stat cards are reused where
# the column is the same figure (the same translation).
COLUMNS = (
    ("time", N_("Time"), "activity", "show_time"),
    ("reviews", N_("Reviews"), "activity", "show_reviews"),
    ("retention", N_("Retention"), "retention", "show_retention"),
    ("ret_young", N_("Ret. Young"), "retention", "show_retention_young"),
    ("ret_mature", N_("Ret. Mature"), "retention", "show_retention_mature"),
    ("ret_true", N_("True Retention"), "retention", None),
    ("buttons", N_("Buttons"), "activity", "show_buttons_dist"),
    ("avg_time", N_("Avg Time"), "activity", "show_avg_time"),
    ("rev_young", N_("Young Reviews"), "activity", None),
    ("rev_mature", N_("Mature Reviews"), "activity", None),
    ("again", N_("Again"), "activity", None),
    ("lapses", N_("Lapses"), "activity", None),
    ("reviews_per_day", N_("Reviews/Day"), "activity", None),
    ("time_per_day", N_("Time/Day"), "activity", None),
    ("reviews_per_active_day", N_("Reviews/Active Day"), "activity", None),
    ("time_per_active_day", N_("Time/Active Day"), "activity", None),
    ("best_day", N_("Best Day"), "activity", None),
    ("longest_streak", N_("Longest Streak"), "activity", "show_longest_streak"),
    ("streak", N_("Streak"), "activity", "show_streak"),
    ("active_days", N_("Active Days"), "activity", "show_active_days"),
    ("days_learned", N_("Days Learned"), "activity", None),
    ("cards_total", N_("Total Cards"), "cards", None),
    ("cards_new", N_("New Cards"), "cards", None),
    ("cards_learning", N_("Learning Cards"), "cards", None),
    ("cards_young", N_("Young Cards"), "cards", None),
    ("cards_mature", N_("Mature Cards"), "cards", None),
    ("cards_suspended", N_("Suspended Cards"), "cards", None),
    ("cards_buried", N_("Buried Cards"), "cards", None),
    ("due_today", N_("Due Today"), "schedule", None),
    ("backlog", N_("Backlog"), "schedule", None),
    ("forecast", N_("Forecast"), "schedule", "show_forecast"),
    ("avg_retrievability", N_("Avg Retrievability"), "schedule", None),
    ("avg_stability", N_("Avg Stability"), "schedule", None),
)
GROUPS = (("activity", N_("Activity")), ("retention", N_("Retention")), ("cards", N_("Cards")),
          ("schedule", N_("Schedule")))
KEYS = tuple(c[0] for c in COLUMNS)
LABELS = {c[0]: c[1] for c in COLUMNS}
FLAGS = {c[0]: c[3] for c in COLUMNS if c[3]}

# A span without the flag shows the column, apart from the streak.
_FLAG_DEFAULTS = {"show_streak": False}

# Figures read from each deck's history cache (its period, its cards, its due cards, FSRS): only computed when one
# of these columns is shown.
HISTORY_KEYS = frozenset({"reviews_per_day", "time_per_day", "reviews_per_active_day", "time_per_active_day", "best_day",
                          "days_learned"})
STATE_KEYS = frozenset({"cards_total", "cards_new", "cards_learning", "cards_young", "cards_mature", "cards_suspended",
                        "cards_buried", "due_today", "backlog", "avg_retrievability", "avg_stability"})


def _first_span(conf):
    from . import DEFAULT_DETAILS_TABS

    tabs = conf.get(Config.DETAILS_TABS_DATA) or DEFAULT_DETAILS_TABS
    shown = [t for t in tabs if isinstance(t, dict) and t.get("enabled", True)]
    return (shown or [t for t in tabs if isinstance(t, dict)] or [{}])[0]


def table_columns(conf):
    """The columns shown (not the deck's), in saved table order."""
    saved = conf.get(Config.TABLE_COLUMNS)
    if isinstance(saved, (list, tuple)):
        seen = set()
        return [k for k in saved if k in LABELS and not (k in seen or seen.add(k))]
    span = _first_span(conf)
    chosen = {k for k, flag in FLAGS.items() if span.get(flag, _FLAG_DEFAULTS.get(flag, True))}
    return [k for k in KEYS if k in chosen]


def table_show_counts(conf):
    saved = conf.get(Config.TABLE_SHOW_COUNTS)
    if isinstance(saved, bool):
        return saved
    return bool(_first_span(conf).get("show_counts", False))


def apply_to_spans(tabs, keys, show_counts):
    """Write the list into each span's old show_* flags (in place)."""
    keys = set(keys)
    for t in tabs or ():
        if not isinstance(t, dict):
            continue
        for k, flag in FLAGS.items():
            t[flag] = k in keys
        t["show_counts"] = bool(show_counts)


# Reset Columns (the table header's menu, Settings > Time Span): the table's first columns, without the counts.
DEFAULT_COLUMNS = ("time", "reviews", "retention", "ret_young", "ret_mature", "buttons", "avg_time",
                   "longest_streak", "active_days", "forecast")
DEFAULT_SHOW_COUNTS = False


def set_table_columns(conf, keys=None, show_counts=None):
    """Change the list in `conf` (and the spans' flags). Returns the config changes, for write_config_vals."""
    import copy

    from . import DEFAULT_DETAILS_TABS

    if keys is None:
        keys = table_columns(conf)
    else:
        seen = set()
        keys = [k for k in keys if k in LABELS and not (k in seen or seen.add(k))]
    show_counts = table_show_counts(conf) if show_counts is None else bool(show_counts)
    tabs = copy.deepcopy(conf.get(Config.DETAILS_TABS_DATA) or DEFAULT_DETAILS_TABS)
    apply_to_spans(tabs, keys, show_counts)
    updates = {Config.TABLE_COLUMNS: keys, Config.TABLE_SHOW_COUNTS: show_counts, Config.DETAILS_TABS_DATA: tabs}
    conf.update(updates)
    return updates
