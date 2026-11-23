# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The collection's decks for the pages' deck lists: Settings > Decks (settings_decks.js) and the deck picker of a
widget's decks (deck_picker.js, the web DeckMultiSelectDialog). No window: a page's handler answers with deck_tree().

A widget's decks: None follows the deck shown (everything checked, deleted cards too), [] every deck but not the
deleted cards, else the ids checked and/or DELETED ("deleted"), as DeckMultiSelectDialog saves them.
"""

from __future__ import annotations

from aqt import mw

from ..details.logic.logger import log_error

DELETED = "deleted"
DEFAULT_DECK = 1


def hidden_default(names=None):
    """True when Anki's deck list leaves out its Default deck (it can't be deleted): no card of its own, no subdeck,
    and other decks there. names: the decks' full names, when already read."""
    try:
        if names is None:
            names = [d.name for d in mw.col.decks.all_names_and_ids()]
        name = mw.col.decks.name(DEFAULT_DECK) or ""
        if len(names) < 2 or any(n.startswith(name + "::") for n in names):
            return False
        return not mw.col.db.scalar(f"select 1 from cards where did = {DEFAULT_DECK} or odid = {DEFAULT_DECK} limit 1")
    except Exception:
        return False


def deck_tree():
    """[{id, name (its own part), path (full name), depth, parent, cards, filtered}], parents before children.
    cards: the deck's own cards (not its subdecks')."""
    counts = {}
    try:
        for did, n in mw.col.db.all("select did, count() from cards group by did"):
            counts[int(did)] = int(n)
    except Exception as e:
        log_error(f"deck tree: card counts {e!r}")
    try:
        items = [(d.name, int(d.id)) for d in mw.col.decks.all_names_and_ids()]
    except Exception:
        items = [(d["name"], int(d["id"])) for d in mw.col.decks.all()]
    if hidden_default([n for n, _ in items]):
        items = [it for it in items if it[1] != DEFAULT_DECK]
    items.sort(key=lambda x: [p.lower() for p in x[0].split("::")])
    by_path = {name: did for name, did in items}
    out = []
    for name, did in items:
        parts = name.split("::")
        parent = by_path.get("::".join(parts[:-1])) if len(parts) > 1 else None
        try:
            filtered = bool(mw.col.decks.get(did, default=False).get("dyn"))
        except Exception:
            filtered = False
        out.append({"id": did, "name": parts[-1], "path": name, "depth": len(parts) - 1, "parent": parent,
                    "cards": counts.get(did, 0), "filtered": filtered})
    return out


def from_page(ids):
    """The page's answer (None, or a list of id strings / "deleted") as a widget's deck_ids."""
    if ids is None:
        return None
    out = []
    for v in ids:
        if v == DELETED:
            out.append(DELETED)
            continue
        try:
            out.append(int(v))
        except (TypeError, ValueError):
            pass
    return out
