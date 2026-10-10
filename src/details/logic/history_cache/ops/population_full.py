# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..shared import datetime, mw, timedelta
from ..exclusion import excluded_dids, drop_total_targets


def populate_full_cache(cfg, range_type, min_rev_id=None, min_card_id=None, include_heavy=True, hier_context=None):
    """The 'Super Query' implementation."""
    from .....utils import rollover_hour
    offset_hour = rollover_hour()
    months_en = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    from ...history_provider import HistoryProvider
    raw_deck_data = HistoryProvider.fetch_all_decks_context(cfg, range_type, min_rev_id=min_rev_id, min_card_id=min_card_id)
    
    if hier_context:
        hier_map, all_decks_info = hier_context
    else:
        # Fallback if not provided (should only happen in full re-init if not called via refresh_incremental)
        all_decks = mw.col.decks.all_names_and_ids()
        all_decks_info = {d.id: d.name for d in all_decks}
        hier_map = {}
        _excl = excluded_dids()
        def get_targets(did):
            t = {did, None, "[[TOTAL]]"}
            name = all_decks_info.get(did)
            if name:
                parts = name.split("::")
                for i in range(1, len(parts)): t.add("::".join(parts[:i]))
            return drop_total_targets(t, did, _excl)
        for d in all_decks:
            for t in get_targets(d.id):
                hier_map.setdefault(t, []).append(d.id)
        hier_map[-1] = [-1]
    
    results = {}
    
    is_delta = min_rev_id is not None
    
    _excluded = excluded_dids()

    def get_targets(did):
        name = all_decks_info.get(did)
        if name:
            # The string name is the primary key for the parent parts. Do not also add the
            # full name: the raw integer did is already included, and both together
            # double-count the leaf deck.
            t = {None, "[[TOTAL]]", did}
            parts = name.split("::")
            for i in range(1, len(parts)):
                t.add("::".join(parts[:i]))
            return drop_total_targets(t, did, _excluded)
        # Fallback to integer ID for decks with no name (e.g. deleted or ID -1)
        return drop_total_targets({did, None, "[[TOTAL]]"}, did, _excluded)
    
    def make_agg():
        return {
            "reviews_map": {}, "added_map": {}, 
            "stats": {k: 0 for k in ["total_reviews", "total_time_ms", "total_passed", "rev_young", "pass_young", "rev_mat", "pass_mat", "learn_count", "relearn_count", "young_count", "mature_count", "cram_count", "again", "hard", "good", "easy"]},
            "counts": {k: 0 for k in ["new", "learn", "relearn", "young", "mature", "buried", "suspended", "deleted", "total"]},
            "future": {}, 
            "distribution": {"learning":[0,0,0,0], "young":[0,0,0,0], "mature":[0,0,0,0]},
            "hourly": {h: {"total": 0, "correct": 0} for h in range(24)},
            "review_intervals": {"distribution": {}, "total": 0},
            "fsrs": {"stability":{}, "difficulty":{}, "retrievability":{}}
        }
    
    aggregators = {}
    
    for leaf_did, leaf_data in raw_deck_data.items():
        targets = get_targets(leaf_did)
        for t_did in targets:
            if t_did not in aggregators: aggregators[t_did] = make_agg()
            agg = aggregators[t_did]
            
            c_revs = leaf_data["reviews"]
            for b_idx, r_data in c_revs.items():
                if b_idx not in agg["reviews_map"]:
                    agg_r = r_data.copy()
                    if "hourly" in r_data:
                        agg_r["hourly"] = {h: rd.copy() for h, rd in r_data["hourly"].items()}
                    agg["reviews_map"][b_idx] = agg_r
                else:
                    target_r = agg["reviews_map"][b_idx]
                    target_r["reviews"] += r_data["reviews"]
                    target_r["time_ms"] += r_data["time_ms"]
                    target_r["passed"] += r_data["passed"]
                    for k in ["rev_young", "pass_young", "rev_mat", "pass_mat", "learn_count", "relearn_count", "young_count", "mature_count", "cram_count", "again", "hard", "good", "easy",
                              "learn_time_ms", "relearn_time_ms", "young_time_ms", "mature_time_ms", "cram_time_ms",
                              "learn_btn1", "learn_btn2", "learn_btn3", "learn_btn4",
                              "young_btn1", "young_btn2", "young_btn3", "young_btn4",
                              "mature_btn1", "mature_btn2", "mature_btn3", "mature_btn4"]:
                        target_r[k] = target_r.get(k, 0) + r_data.get(k, 0)
                        
                    if "hourly" in r_data:
                        tgt_h = target_r.setdefault("hourly", {h: {"total": 0, "correct": 0} for h in range(24)})
                        src_h = r_data["hourly"]
                        for h in range(24):
                            if h in src_h:
                                tgt_h[h]["total"] += src_h[h]["total"]
                                tgt_h[h]["correct"] += src_h[h]["correct"]
            
            for b_idx, cnt in leaf_data.get("added", {}).items():
                agg["added_map"][b_idx] = agg["added_map"].get(b_idx, 0) + cnt
            
            c_stats = leaf_data.get("stats", {})
            for k in agg["stats"]: agg["stats"][k] += c_stats.get(k, 0)
    
            # Full builds must always populate snapshot fields (counts/future/etc),
            # including when hierarchy context is precomputed by caller.
            if not is_delta:
                c_counts = leaf_data["counts"]
                for k in agg["counts"]: agg["counts"][k] += c_counts.get(k, 0)
                for due, cnt in leaf_data["future"].items():
                    agg["future"][due] = agg["future"].get(due, 0) + cnt
                for ctype, e_counts in leaf_data.get("distribution", {}).items():
                    if ctype in agg["distribution"]:
                        for i in range(4): agg["distribution"][ctype][i] += e_counts[i]
                
                for h_idx, h_data in leaf_data.get("hourly", {}).items():
                    agg["hourly"][h_idx]["total"] += h_data["total"]
                    agg["hourly"][h_idx]["correct"] += h_data["correct"]
                
                li_dist = leaf_data.get("review_intervals", {}).get("distribution", {})
                for ivl, cnt in li_dist.items():
                    agg["review_intervals"]["distribution"][ivl] = agg["review_intervals"]["distribution"].get(ivl, 0) + cnt
                    agg["review_intervals"]["total"] += cnt
                    
                l_fsrs = leaf_data.get("fsrs", {})
                for fs_key in ["stability", "difficulty", "retrievability"]:
                    l_fs_data = l_fsrs.get(fs_key, {})
                    for val, cnt in l_fs_data.items():
                        agg["fsrs"][fs_key][val] = agg["fsrs"][fs_key].get(val, 0) + cnt
    
    for t_did, agg in aggregators.items():
        reviews_map = agg["reviews_map"]
        sorted_bins = sorted(reviews_map.keys(), reverse=True)
        
        history_list = []
        for b_idx in sorted_bins:
            r_data = reviews_map[b_idx]
            dt = datetime.fromtimestamp(b_idx / 1000)
            l_date = dt.strftime("%Y-%m-%d")
            
            history_list.append({
                "date": l_date,
                "pretty_date": f"{months_en[dt.month-1]} {dt.day:02d}, {dt.year}",
                "logical_date": l_date,
                **r_data,
                "retention": (r_data["passed"] / r_data["reviews"] * 100) if r_data["reviews"] > 0 else None,
                "ret_young": (r_data["pass_young"] / r_data["rev_young"] * 100) if r_data.get("rev_young", 0) > 0 else None,
                "ret_mat": (r_data["pass_mat"] / r_data["rev_mat"] * 100) if r_data.get("rev_mat", 0) > 0 else None,
                "learning_buttons": [r_data.get("learn_btn1", 0), r_data.get("learn_btn2", 0), r_data.get("learn_btn3", 0), r_data.get("learn_btn4", 0)],
                "young_buttons": [r_data.get("young_btn1", 0), r_data.get("young_btn2", 0), r_data.get("young_btn3", 0), r_data.get("young_btn4", 0)],
                "mature_buttons": [r_data.get("mature_btn1", 0), r_data.get("mature_btn2", 0), r_data.get("mature_btn3", 0), r_data.get("mature_btn4", 0)]
            })
    
        added_list = []
        if agg["added_map"]:
            curr_cum = 0
            temp_added = []
            for b_idx in sorted(agg["added_map"].keys()):
                count = agg["added_map"][b_idx]
                curr_cum += count
                dt = datetime.fromtimestamp(b_idx / 1000)
                temp_added.append({
                    "date": dt.strftime("%Y-%m-%d"),
                    "pretty_date": f"{months_en[dt.month-1]} {dt.day:02d}, {dt.year}",
                    "count": count, "cumulative": curr_cum
                })
            added_list = temp_added[::-1]
    
        active_days_count = 0
        current_streak = 0
        
        if sorted_bins:
            now_dt = datetime.now()
            if now_dt.hour < offset_hour: now_dt -= timedelta(days=1)
            today_date = now_dt.date()
            yesterday_date = today_date - timedelta(days=1)
            
            last_bin = sorted_bins[0]
            last_date = datetime.fromtimestamp(last_bin / 1000).date()
            
            if last_date == today_date or last_date == yesterday_date:
                if reviews_map[last_bin].get("reviews", 0) > 0:
                    current_streak = 1
                    prev_date = last_date
                    for b_idx in sorted_bins[1:]:
                        r_data = reviews_map.get(b_idx)
                        if not r_data or r_data.get("reviews", 0) <= 0: continue
                        cur_date = datetime.fromtimestamp(b_idx / 1000).date()
                        diff_days = (prev_date - cur_date).days
                        
                        if diff_days == 1:
                            current_streak += 1
                            prev_date = cur_date
                        elif diff_days == 0:
                            continue
                        else:
                            break
                            
            for b_idx in sorted_bins:
                if reviews_map[b_idx].get("reviews", 0) > 0:
                    active_days_count += 1
    
        ri_agg = agg["review_intervals"]
        p50, p95 = 31, 365
        if ri_agg["total"] > 0:
            sorted_ivls = sorted(ri_agg["distribution"].items())
            curr = 0
            found_p50 = False
            found_p95 = False
            for ivl, count in sorted_ivls:
                curr += count
                if not found_p50 and curr >= ri_agg["total"] * 0.5:
                    p50 = ivl
                    found_p50 = True
                if not found_p95 and curr >= ri_agg["total"] * 0.95:
                    p95 = ivl
                    found_p95 = True
                if found_p50 and found_p95:
                    break
        ri_agg["p50"] = p50
        ri_agg["p95"] = p95
    
        results[t_did] = {
            range_type: {
                "reviews": history_list, "added": added_list,
                "added_dates": [a["date"] for a in added_list],
                "stats": {**agg["stats"], "active_days": active_days_count, "streak": current_streak},
                "distribution": agg["distribution"],
                "hourly": agg["hourly"],
                "review_intervals": ri_agg,
                "fsrs": agg["fsrs"],
                "is_dense": False
            }
        }
        
        if not is_delta:
            ctx = results[t_did][range_type]
            ctx["counts"] = agg["counts"]
            ctx["distribution"] = agg["distribution"]
            ctx["hourly"] = agg["hourly"]
            # review_intervals is already set in results[t_did][range_type] above with percentiles
            ctx["fsrs"] = agg["fsrs"]
            
            fd_total = sum(agg["future"].values())
            ctx["future_due"] = {
                "distribution": agg["future"], "total": fd_total,
                "average": fd_total / max(1, 365), "tomorrow": agg["future"].get(1, 0), "max_days": 3650
            }
    return results, hier_map
    
    

