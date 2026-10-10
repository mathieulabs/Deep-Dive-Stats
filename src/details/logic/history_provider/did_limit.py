# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .shared import Config, mw


class DidLimitMixin:
    @staticmethod
    def _get_did_limit(addon_config, deck_id):
        """Deck id limit string used in the queries."""
        from ....utils import sql_id_list
        if deck_id == -1:
             return "AND (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END) IS NULL"
        elif deck_id in [0, "0", None]:
             from ....utils import excluded_not_in_clause
             return excluded_not_in_clause(addon_config.config.get(Config.EXCLUDED_DECKS, []))
        elif isinstance(deck_id, str):
             all_decks = mw.col.decks.all_names_and_ids()
             dids = [d.id for d in all_decks if d.name == deck_id or d.name.startswith(deck_id + "::")]
             if not dids: return ""
             return f"AND (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END) IN {sql_id_list(dids)}"
        elif isinstance(deck_id, list):
             # Multi-deck selection: list of int deck IDs and/or "deleted" token
             from ....utils import sql_id_list as _afi2
             include_deleted = "deleted" in deck_id
             numeric_ids = [d for d in deck_id if isinstance(d, int)]
             all_dids: set[int] = set()
             for did in numeric_ids:
                 try:
                     all_dids.update(mw.col.decks.deck_and_child_ids(did))
                 except Exception:
                     continue  # deck was deleted since it was selected
             if not all_dids and not include_deleted:
                 return ""  # empty selection = no filter
             parts = []
             if all_dids:
                 parts.append(f"(CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END) IN {_afi2(list(all_dids))}")
             if include_deleted:
                 parts.append("(CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END) IS NULL")
             if len(parts) == 1:
                 return f"AND {parts[0]}"
             return f"AND ({' OR '.join(parts)})"
        else:
             try:
                 dids = mw.col.decks.deck_and_child_ids(deck_id)
             except Exception:
                 # The selected deck no longer exists: match no cards instead of crashing.
                 return "AND 0"
             return f"AND (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END) IN {sql_id_list(dids)}"


