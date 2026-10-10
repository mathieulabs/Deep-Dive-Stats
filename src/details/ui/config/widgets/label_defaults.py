# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations


from ....widgets.stats_cards.logic.model import STAT_CARD_INFO_MAP, get_stat_card_default_title


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


def get_default_label(dialog) -> str:
    """Identify the default label for the current widget type/metric."""
    wtype = resolve_widget_type(dialog)
    if wtype == "stat_card":
        stat_key = dialog.widget_def.get("stat_key")
        if hasattr(dialog, "stat_key_combo"):
            stat_key = dialog.stat_key_combo.currentData()
        if stat_key not in STAT_CARD_INFO_MAP:
            return "Stat Card"
        return get_stat_card_default_title(stat_key)

    default_labels = {
        "activity": "Activity",
        "retention": "Retention",
        "heatmap": "Heatmap",
        "added": "Added",
        "distribution": "Answer Buttons",
        "card_counts": "Card Counts",
        "hourly": "Hourly Breakdown",
        "future_due": "Future Due",
        "review_intervals": "Review Intervals",
        "stability": "Stability",
        "difficulty": "Difficulty",
        "retrievability": "Retrievability",
        "text_label": "Text Widget",
    }
    return default_labels.get(wtype, wtype.replace("_", " ").title())


def reset_label(dialog) -> None:
    """Restore default label to the input field, including deck name if bound."""
    default_label = get_default_label(dialog)

    dialog.label_edit.setText(default_label)
    dialog.apply_live_changes()


def update_reset_button_visibility(dialog) -> None:
    """Show reset button only if there is a custom label."""
    if hasattr(dialog, "reset_label_btn"):
        current = dialog.label_edit.text().strip().upper()
        default = get_default_label(dialog).upper()
        dialog.reset_label_btn.setVisible(bool(current) and current != default)

