# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
def build_initial_fetch_queue(tab_widget, deck_tree, deleted_tab_did="__deleted_cards__"):
    """Build fetch queue with current tab first and heavy aggregate tabs deferred."""
    all_queue_dids = [d["did"] for d in deck_tree]
    current_tab = tab_widget.widget(tab_widget.currentIndex())
    current_did = current_tab.property("deck_id") if current_tab else None
    special_dids = {"collection", deleted_tab_did}

    regular = [did for did in all_queue_dids if did not in special_dids and did != current_did]
    special = [did for did in all_queue_dids if did in special_dids and did != current_did]
    queue = ([current_did] if current_did in all_queue_dids else []) + regular + special
    return queue
