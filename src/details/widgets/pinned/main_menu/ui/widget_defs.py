# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from aqt import mw
from .....ui import Period
from .....logic import log_debug
from .....logic.logger import log_swallowed


def default_span_for_widget_type(widget_type):
    if widget_type in ("stat_card", "stat_cards"):
        return Period.TOTAL
    return Period.YEAR


def normalize_time_span(span, widget_type):
    if span is None:
        return default_span_for_widget_type(widget_type)

    allowed = {
        Period.TOTAL,
        Period.WEEK,
        Period.TWO_WEEKS,
        Period.MONTH,
        Period.YEAR,
        Period.CUSTOM,
        Period.TODAY,
        Period.YESTERDAY,
        Period.LAST_YEAR,
        Period.THREE_MONTHS,
    }

    resolved = None
    if isinstance(span, int):
        resolved = span
    elif isinstance(span, str):
        cleaned = span.strip()
        lowered = cleaned.lower()
        if cleaned.lstrip("-").isdigit():
            resolved = int(cleaned)
        else:
            name_map = {
                "total": Period.TOTAL,
                "past week": Period.WEEK,
                "week": Period.WEEK,
                "past 2 weeks": Period.TWO_WEEKS,
                "2 weeks": Period.TWO_WEEKS,
                "two weeks": Period.TWO_WEEKS,
                "past month": Period.MONTH,
                "month": Period.MONTH,
                "past year": Period.YEAR,
                "year": Period.YEAR,
                "custom": Period.CUSTOM,
                "today": Period.TODAY,
                "yesterday": Period.YESTERDAY,
                "last year": Period.LAST_YEAR,
                "past 3 months": Period.THREE_MONTHS,
                "3 months": Period.THREE_MONTHS,
                "three months": Period.THREE_MONTHS,
            }
            resolved = name_map.get(lowered)

    if isinstance(resolved, int):
        if resolved in allowed:
            return resolved
        if 1000 <= resolved <= 9999:
            return resolved
        from .....logic.data.core.abs_period import is_abs
        if is_abs(resolved):
            return resolved

    return default_span_for_widget_type(widget_type)


def normalized_widget_def(widget_def):
    normalized = dict(widget_def)
    wtype = normalized.get("type", "")
    normalized["time_span"] = normalize_time_span(normalized.get("time_span"), wtype)
    return normalized


def widget_allowed_in_context(widget_def, deck_id, is_deck_browser):
    """Return True if widget should be visible for the current context."""
    view_dids = widget_def.get("view_dids", None)
    if not view_dids:
        return True

    try:
        view_set = set()
        for v in (view_dids or []):
            if v == "main_menu":
                view_set.add("main_menu")
            else:
                view_set.add(int(v))
    except Exception:
        return True

    if deck_id is None and bool(is_deck_browser):
        return "main_menu" in view_set

    if deck_id is None:
        # Transient state after review/refresh can briefly leave deck_id unset.
        # Keep widgets visible by fallback instead of clearing the overlay.
        try:
            selected = mw.col.decks.selected() if (mw and mw.col and mw.col.decks) else None
            if selected is not None:
                return int(selected) in view_set
        except Exception:
            log_swallowed()
        log_debug(
            f"context fallback: deck_id=None is_deck_browser={is_deck_browser} allowing widget_id={widget_def.get('id')}",
            tag="PINNED",
        )
        return True

    try:
        return int(deck_id) in view_set
    except Exception:
        return False

