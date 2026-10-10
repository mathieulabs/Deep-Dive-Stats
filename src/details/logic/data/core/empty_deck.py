# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Cheap check used to skip full revlog scans for decks that hold no cards."""
from aqt import mw


def did_limit_has_no_cards(did_limit):
    """True when did_limit selects specific decks and none of them holds a card.

    A deck without cards has no review history either, so the revlog queries
    behind it can only return nothing. Other filters (all decks, excluded decks,
    deleted cards) are never treated as empty.
    """
    if not did_limit or " IN (" not in did_limit or "NOT IN" in did_limit or "IS NULL" in did_limit:
        return False
    try:
        return mw.col.db.scalar(f"SELECT 1 FROM cards WHERE 1=1 {did_limit} LIMIT 1") is None
    except Exception:
        return False
