# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations


from ....logic.stat_cards import STAT_CARD_INFO_MAP, get_stat_card_default_title
from .....i18n import tr, N_, tr_name


def resolve_widget_type(dialog) -> str:
    """Resolve a stable widget type even for old saved entries with type='unknown'."""
    wtype = str(getattr(dialog, "type", "") or "").strip().lower()
    if wtype and wtype != "unknown":
        return wtype

    raw_id = str((dialog.widget_def or {}).get("id", "") or "").strip().lower()
    if raw_id.endswith("_g"):
        raw_id = raw_id[:-2]
    if raw_id:
        known = {
            "activity",
            "retention",
            "heatmap",
            "added",
            "distribution",
            "card_counts",
            "hourly",
            "future_due",
            "review_intervals",
            "stability",
            "difficulty",
            "retrievability",
            "stat_card",
        }
        known.add("text_label")
        if raw_id in known:
            return raw_id

    return wtype or "widget"


# Default name of each widget type, stored in English and shown with tr_name().
DEFAULT_LABELS = {
    "activity": N_("Activity"),
    "retention": N_("Retention"),
    "heatmap": N_("Heatmap"),
    "added": N_("Added"),
    "distribution": N_("Answer Buttons"),
    "card_counts": N_("Card Counts"),
    "hourly": N_("Hourly Breakdown"),
    "future_due": N_("Future Due"),
    "review_intervals": N_("Review Intervals"),
    "stability": N_("Stability"),
    "difficulty": N_("Difficulty"),
    "retrievability": N_("Retrievability"),
    "text_label": N_("Text Widget"),
}
# Names that older versions saved when pinning a chart from the Deep Dive.
OLD_PINNED_NAMES = (N_("Hourly"), N_("Distribution"))


def get_default_label(dialog) -> str:
    """Identify the default label for the current widget type/metric."""
    wtype = resolve_widget_type(dialog)
    if wtype == "stat_card":
        stat_key = dialog.widget_def.get("stat_key")
        if stat_key not in STAT_CARD_INFO_MAP:
            return tr("Stat Card")
        return get_stat_card_default_title(stat_key)

    return tr_name(DEFAULT_LABELS.get(wtype, wtype.replace("_", " ").title()))
