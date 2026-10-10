# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Deck-tree transformation helpers."""

from aqt import mw
from ...logger import log_swallowed

def process_deck_tree(results, prev_stats_map, activity_map, retention_maps, deck_limits, remaining_new_map, bin_labels, bin_count, show_trends, streak_map=None, deck_name_maps=None):
    """
    Builds the deck tree structure, aggregates stats for folders, and flattens it for display.
    deck_name_maps: optional tuple (did_to_name, name_to_did) pre-computed on main thread.
    """
    if streak_map is None: streak_map = {}
    
    # tree_data: { full_name: { stats } }
    tree_data = {}
    
    # Use precomputed maps when available (avoids touching mw.col from a background thread).
    if deck_name_maps is not None:
        did_to_name, name_to_did = deck_name_maps
    else:
        all_decks = mw.col.decks.all_names_and_ids()
        name_to_did = {d.name: d.id for d in all_decks}
        did_to_name = {d.id: d.name for d in all_decks}
    
    for res in results:
        did = res[0]
        if did is None:
            # Deleted cards - special case, no hierarchy
            ps = prev_stats_map.get(did, [0]*13)
            indices = set(int(x) for x in str(res[12]).split(",") if x) if res[12] else set()
            
            tree_data["[[Deleted]]"] = {
                "is_deleted": True, "full_name": "Deleted Cards", "depth": 0, "parent": None, "has_children": False,
                "did": None, "time_ms": res[1], "reviews": res[2], "passed": res[3], "pass_young": res[4], "rev_young": res[5],
                "pass_mat": res[6], "rev_mat": res[7], "again": res[8] or 0, "hard": res[9] or 0, "good": res[10] or 0, "easy": res[11] or 0,
                "active_days": len(indices), "active_days_set": indices,
                "streak_current": 0, "streak_longest": 0,
                "prev_time_ms": ps[1] or 0, "prev_reviews": ps[2] or 0, "prev_passed": ps[3] or 0,
                "new_limit": 0, # Deleted cards don't have limits
                "remaining_new": remaining_new_map.get(did, 0),
            }
            continue

        full_name = did_to_name.get(did, "Unknown")
        parts = full_name.split("::")
        
        for i in range(1, len(parts) + 1):
            path = "::".join(parts[:i])
            if path not in tree_data:
                tree_data[path] = {
                    "is_deleted": False, "full_name": path, "display_name": parts[i-1], "depth": i-1, "parent": "::".join(parts[:i-1]) if i > 1 else None,
                    "has_children": False, 
                    "did": name_to_did.get(path),
                    "time_ms": 0, "reviews": 0, "passed": 0, "pass_young": 0, "rev_young": 0, "pass_mat": 0, "rev_mat": 0, "again": 0, "hard": 0, "good": 0, "easy": 0, "active_days": 0, "active_days_set": set(),
                    "prev_time_ms": 0, "prev_reviews": 0, "prev_passed": 0,
                    "prev_pass_young": 0, "prev_rev_young": 0, "prev_pass_mat": 0, "prev_rev_mat": 0,
                    "new_limit": 0, "remaining_new": 0,
                    "streak_current": 0, "streak_longest": 0,
                    "leaf_did": None,
                    "has_current_data": False,
                    "max_days": 0
                }
            
            td = tree_data[path]
            if i == len(parts):
                td["did"] = did
                td["leaf_did"] = did
            
            td["time_ms"] += res[1] or 0
            td["reviews"] += res[2] or 0
            td["passed"] += res[3] or 0
            td["pass_young"] += res[4] or 0
            td["rev_young"] += res[5] or 0
            td["pass_mat"] += res[6] or 0
            td["rev_mat"] += res[7] or 0
            td["again"] += res[8] or 0
            td["hard"] += res[9] or 0
            td["good"] += res[10] or 0
            td["easy"] += res[11] or 0
            if res[12]:
                 try:
                     indices = set(int(x) for x in str(res[12]).split(",") if x)
                     td["active_days_set"].update(indices)
                     td["active_days"] = len(td["active_days_set"])
                 except Exception: log_swallowed()
            td["has_current_data"] = True
            
            td["new_limit"] += deck_limits.get(did, 0)
            td["remaining_new"] += remaining_new_map.get(did, 0)
            
            limit = deck_limits.get(did, 0)
            if limit > 0:
                rem = remaining_new_map.get(did, 0)
                td["max_days"] = max(td["max_days"], rem / limit)

            # Streaks are not additive: a folder shows the best streak in its subtree.
            c_s, l_s = streak_map.get(did, (0, 0))
            td["streak_current"] = max(td["streak_current"], c_s)
            td["streak_longest"] = max(td["streak_longest"], l_s)
            
    if show_trends:
        for did, pr in prev_stats_map.items():
            if did is None:
                if "[[Deleted]]" in tree_data:
                    td = tree_data["[[Deleted]]"]
                    td["prev_time_ms"] = pr[1] or 0
                    td["prev_reviews"] = pr[2] or 0
                    td["prev_passed"] = pr[3] or 0
                    td["prev_pass_young"] = pr[4] or 0
                    td["prev_rev_young"] = pr[5] or 0
                    td["prev_pass_mat"] = pr[6] or 0
                    td["prev_rev_mat"] = pr[7] or 0
                continue

            full_name = did_to_name.get(did, "Unknown")
            parts = full_name.split("::")
            for i in range(1, len(parts) + 1):
                path = "::".join(parts[:i])
                if path not in tree_data:
                    # Create missing path if it was only in previous period
                    tree_data[path] = {
                        "is_deleted": False, "full_name": path, "display_name": parts[i-1], "depth": i-1, "parent": "::".join(parts[:i-1]) if i > 1 else None,
                        "has_children": False, "did": None, "time_ms": 0, "reviews": 0, "passed": 0, "pass_young": 0, "rev_young": 0, "pass_mat": 0, "rev_mat": 0, "again": 0, "hard": 0, "good": 0, "easy": 0, "active_days": 0,
                        "prev_time_ms": 0, "prev_reviews": 0, "prev_passed": 0, "prev_pass_young": 0, "prev_rev_young": 0, "prev_pass_mat": 0, "prev_rev_mat": 0,
                        "new_limit": 0, "remaining_new": 0,
                        "streak_current": 0, "streak_longest": 0,
                        "leaf_did": None, "has_current_data": False, "active_days_set": set()
                    }
                
                td = tree_data[path]
                td["prev_time_ms"] += pr[1] or 0
                td["prev_reviews"] += pr[2] or 0
                td["prev_passed"] += pr[3] or 0
                td["prev_pass_young"] += pr[4] or 0
                td["prev_rev_young"] += pr[5] or 0
                td["prev_pass_mat"] += pr[6] or 0
                td["prev_rev_mat"] += pr[7] or 0

    for path in tree_data:
        parent = tree_data[path]["parent"]
        if parent in tree_data:
            tree_data[parent]["has_children"] = True

    flattened_results = []
    if "[[Deleted]]" in tree_data:
        flattened_results.append(tree_data["[[Deleted]]"])
        tree_data["[[Deleted]]"]["tree_prefix"] = ""

    def add_children(parent_path, prefix):
        children = [p for p in tree_data if tree_data[p]["parent"] == parent_path]
        children.sort(key=lambda p: tree_data[p]["time_ms"], reverse=True)
        
        count = len(children)
        for i, child_path in enumerate(children):
            is_last = (i == count - 1)
            curr_prefix = "└── " if is_last else "├── "
            child_prefix_add = "    " if is_last else "│   "
            
            node_prefix = prefix + curr_prefix
            next_prefix = prefix + child_prefix_add
            
            tree_data[child_path]["tree_prefix"] = node_prefix
            flattened_results.append(tree_data[child_path])
            
            add_children(child_path, next_prefix)

    roots = [p for p in tree_data if tree_data[p]["parent"] is None and p != "[[Deleted]]"]
    roots.sort(key=lambda p: tree_data[p]["time_ms"], reverse=True)
    for root in roots:
        tree_data[root]["tree_prefix"] = ""
        flattened_results.append(tree_data[root])
        add_children(root, "")
        
    return flattened_results, tree_data


