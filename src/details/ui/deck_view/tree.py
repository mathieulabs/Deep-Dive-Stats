# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .. import Config


def build_deck_tree(dialog, all_dids, deleted_tab_did="__deleted_cards__"):
    """Build ordered hierarchical deck entries for deck-view tabs."""
    excluded_ids = dialog.addon_config.config.get(Config.EXCLUDED_DECKS, [])
    include_deleted = dialog.addon_config.config.get(Config.INCLUDE_DELETED_CARDS, True)

    deck_tree = [{"did": "collection", "name": "Collection", "depth": 0, "is_folder": False}]
    if include_deleted and "deleted" not in excluded_ids:
        deck_tree.append(
            {"did": deleted_tab_did, "name": "Deleted Cards", "depth": 0, "is_folder": False}
        )

    all_decks = dialog.mw.col.decks.all_names_and_ids() if hasattr(dialog, "mw") else None
    if all_decks is None:
        from aqt import mw

        all_decks = mw.col.decks.all_names_and_ids()

    did_to_name = {d.id: d.name for d in all_decks}
    name_to_did = {d.name: d.id for d in all_decks}

    processed_paths = set()
    folder_parent_paths = set()
    for did in all_dids:
        if did is None or did == "collection":
            continue
        full_name = did_to_name.get(did)
        if not full_name:
            continue

        parts = full_name.split("::")
        for i in range(1, len(parts) + 1):
            path = "::".join(parts[:i])
            if path in processed_paths:
                continue
            processed_paths.add(path)
            if i < len(parts):
                folder_parent_paths.add(path)

            deck_tree.append(
                {
                    "did": name_to_did.get(path),
                    "full_name": path,
                    "name": parts[i - 1],
                    "depth": i - 1,
                    "is_folder": False,
                }
            )

    deck_tree.sort(key=lambda x: x.get("full_name", x["name"]).lower())
    for deck_info in deck_tree:
        path = deck_info.get("full_name")
        if path:
            deck_info["is_folder"] = path in folder_parent_paths

    special = [d for d in deck_tree if d["did"] in ("collection", deleted_tab_did)]
    others = [d for d in deck_tree if d["did"] not in ("collection", deleted_tab_did)]
    return special + others
