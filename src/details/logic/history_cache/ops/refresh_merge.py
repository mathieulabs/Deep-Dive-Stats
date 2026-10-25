# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..shared import Period

def merge_delta(cache, delta_map, is_undo=False):
    """Merges new reviews into existing TOTAL cache entries."""
    from datetime import datetime, timedelta
    from .....utils import rollover_hour
    now_date = datetime.now()
    if now_date.hour < rollover_hour(): now_date -= timedelta(days=1)
    today_str = now_date.strftime("%Y-%m-%d")
    yesterday_str = (now_date - timedelta(days=1)).strftime("%Y-%m-%d")

    for did, delta_ctx in delta_map.items():
        if did not in cache.cache:
            cache.cache[did] = delta_ctx
            continue

        existing_cache = cache.cache[did]
        total_ctx = existing_cache.setdefault(Period.TOTAL, {
            "reviews": [], "heatmap_data": {}, "counts": {}, "stats": {
                "total_reviews": 0, "total_time_ms": 0, "total_passed": 0,
                "rev_young": 0, "pass_young": 0, "rev_mat": 0, "pass_mat": 0,
                "active_days": 0, "streak": 0
            }
        })
        # Older cache blobs / partial contexts may miss these keys.
        # Make sure they exist so delta merge never crashes.
        total_ctx.setdefault("counts", {})
        total_ctx.setdefault("stats", {})

        new_total = delta_ctx.get(Period.TOTAL, {})

        total_ctx["counts"] = new_total.get("counts", total_ctx["counts"])
        total_ctx["future_reviews"] = new_total.setdefault("future_reviews", {})
        total_ctx["future_list"] = new_total.setdefault("future_list", [])
        total_ctx["future_dates"] = new_total.setdefault("future_dates", [])

        # Merge the reviews list (kept in descending order), skipping dates we already have.
        new_history = new_total.get("reviews", [])
        existing_history = total_ctx.get("reviews", [])

        merge_map = {item["logical_date"]: item for item in existing_history}
        # Days that already had reviews. A dense cache also holds empty days (today before
        # its first review), which still count as new active days.
        orig_existing_dates = {d for d, item in merge_map.items() if (item.get("reviews") or 0) > 0}

        if is_undo:
            merge_map.pop(today_str, None)
            merge_map.pop(yesterday_str, None)

        # A delta update adds the new data to existing bins, so other decks' data for the same day in the global view is not overwritten.
        for new_item in new_history:
            ld = new_item.get("logical_date")
            if not ld: continue

            if not is_undo and ld in merge_map:
                target = merge_map[ld]
                for k in ["reviews", "time_ms", "passed", "rev_young", "pass_young", "rev_mat", "pass_mat", "learn_count", "relearn_count", "young_count", "mature_count", "cram_count", "again", "hard", "good", "easy",
                          "learn_time_ms", "relearn_time_ms", "young_time_ms", "mature_time_ms", "cram_time_ms",
                          "learn_btn1", "learn_btn2", "learn_btn3", "learn_btn4",
                          "young_btn1", "young_btn2", "young_btn3", "young_btn4",
                          "mature_btn1", "mature_btn2", "mature_btn3", "mature_btn4"]:
                    target[k] = target.get(k, 0) + new_item.get(k, 0)

                target["retention"] = (target["passed"] / target["reviews"] * 100) if target["reviews"] > 0 else None
                target["ret_young"] = (target["pass_young"] / target["rev_young"] * 100) if target["rev_young"] > 0 else None
                target["ret_mat"] = (target["pass_mat"] / target["rev_mat"] * 100) if target["rev_mat"] > 0 else None

                if "hourly" in new_item:
                    tgt_h = target.setdefault("hourly", {h: {"total": 0, "correct": 0} for h in range(24)})
                    src_h = new_item["hourly"]
                    for h in range(24):
                        if h in src_h:
                            tgt_h[h]["total"] += src_h[h]["total"]
                            tgt_h[h]["correct"] += src_h[h]["correct"]
            else:
                merge_map[ld] = new_item.copy()
                if "hourly" in new_item:
                    merge_map[ld]["hourly"] = {h: new_item["hourly"][h].copy() for h in new_item["hourly"]}

        # Sparse cache for performance, densification happens lazily in get_context
        merged_list = sorted(list(merge_map.values()), key=lambda x: x["logical_date"], reverse=True)

        total_ctx["reviews"] = merged_list
        merged_history = merged_list

        d_stats = new_total.get("stats", {})
        e_stats = total_ctx["stats"]

        need_streak_recalc = is_undo

        if is_undo:
            # Full recalc: data was removed, can't increment
            for k in ["total_reviews", "total_time_ms", "total_passed", "rev_young", "pass_young", "rev_mat", "pass_mat"]:
                e_stats[k] = 0
            for h in merged_history:
                e_stats["total_reviews"] += h.get("reviews", 0)
                e_stats["total_time_ms"] += h.get("time_ms", 0)
                e_stats["total_passed"] += h.get("passed", 0)
                e_stats["rev_young"] += h.get("rev_young", 0)
                e_stats["pass_young"] += h.get("pass_young", 0)
                e_stats["rev_mat"] += h.get("rev_mat", 0)
                e_stats["pass_mat"] += h.get("pass_mat", 0)
            e_stats["active_days"] = sum(1 for h in merged_history if h.get("reviews", 0) > 0)
        elif "total_reviews" not in e_stats:
            # Uninitialized cache, fall back to full-pass for safety
            for k in ["total_reviews", "total_time_ms", "total_passed", "rev_young", "pass_young", "rev_mat", "pass_mat"]:
                e_stats[k] = 0
            for h in merged_history:
                e_stats["total_reviews"] += h.get("reviews", 0)
                e_stats["total_time_ms"] += h.get("time_ms", 0)
                e_stats["total_passed"] += h.get("passed", 0)
                e_stats["rev_young"] += h.get("rev_young", 0)
                e_stats["pass_young"] += h.get("pass_young", 0)
                e_stats["rev_mat"] += h.get("rev_mat", 0)
                e_stats["pass_mat"] += h.get("pass_mat", 0)
            e_stats["active_days"] = sum(1 for h in merged_history if h.get("reviews", 0) > 0)
            need_streak_recalc = True
        else:
            # Incremental: each new_item carries delta amounts (augmented bins hold only the added counts, new bins their full counts), so add them to the existing totals.
            new_dates_added = set()
            for new_item in new_history:
                ld = new_item.get("logical_date")
                if not ld:
                    continue
                e_stats["total_reviews"] = e_stats.get("total_reviews", 0) + new_item.get("reviews", 0)
                e_stats["total_time_ms"] = e_stats.get("total_time_ms", 0) + new_item.get("time_ms", 0)
                e_stats["total_passed"] = e_stats.get("total_passed", 0) + new_item.get("passed", 0)
                e_stats["rev_young"] = e_stats.get("rev_young", 0) + new_item.get("rev_young", 0)
                e_stats["pass_young"] = e_stats.get("pass_young", 0) + new_item.get("pass_young", 0)
                e_stats["rev_mat"] = e_stats.get("rev_mat", 0) + new_item.get("rev_mat", 0)
                e_stats["pass_mat"] = e_stats.get("pass_mat", 0) + new_item.get("pass_mat", 0)
                if ld not in orig_existing_dates and new_item.get("reviews", 0) > 0:
                    new_dates_added.add(ld)
            e_stats["active_days"] = e_stats.get("active_days", 0) + len(new_dates_added)
            # Streak only changes when today or yesterday gets its first-ever review.
            # (Readers recount it anyway, see context_stats, so a stale value is harmless.)
            need_streak_recalc = bool(new_dates_added & {today_str, yesterday_str})

        if need_streak_recalc:
            active_dates = [h["logical_date"] for h in merged_history if h.get("reviews", 0) > 0]
            current_streak = 0
            if active_dates:
                last_date = active_dates[0]
                if last_date == today_str or last_date == yesterday_str:
                    current_streak = 1
                    curr_dt = datetime.strptime(last_date, "%Y-%m-%d").date()
                    for d_str in active_dates[1:]:
                        prev_dt = datetime.strptime(d_str, "%Y-%m-%d").date()
                        diff = (curr_dt - prev_dt).days
                        if diff == 1:
                            current_streak += 1
                            curr_dt = prev_dt
                        elif diff == 0:
                            continue
                        else:
                            break
            e_stats["streak"] = current_streak

        e_stats["retention"] = (e_stats["total_passed"] / e_stats["total_reviews"] * 100) if e_stats.get("total_reviews", 0) > 0 else 0
        e_stats["ret_young"] = (e_stats["pass_young"] / e_stats["rev_young"] * 100) if e_stats.get("rev_young", 0) > 0 else 0
        e_stats["ret_mat"] = (e_stats["pass_mat"] / e_stats["rev_mat"] * 100) if e_stats.get("rev_mat", 0) > 0 else 0

        new_hm = new_total.get("heatmap_data", {})
        existing_hm = total_ctx.setdefault("heatmap_data", {})

        if is_undo:
            existing_hm.pop(today_str, None)
            existing_hm.pop(yesterday_str, None)

        for date_key, entry in new_hm.items():
            existing_hm[date_key] = entry

        new_added = new_total.get("added", [])
        existing_added = total_ctx.get("added", [])

        if new_added or existing_added:
            a_merge_map = {item["date"]: item for item in existing_added}

            if is_undo:
                a_merge_map.pop(today_str, None)
                a_merge_map.pop(yesterday_str, None)

            for item in new_added:
                a_merge_map[item["date"]] = item

            a_sorted_dates = sorted(a_merge_map.keys())
            if a_sorted_dates:
                dense_added = []
                curr_cum = 0
                for d_str in a_sorted_dates:
                    entry = a_merge_map[d_str]
                    curr_cum += entry.get("count", 0)
                    entry["cumulative"] = curr_cum
                    dense_added.append(entry)

                total_ctx["added"] = dense_added[::-1]
                total_ctx["added_dates"] = [a["date"] for a in total_ctx["added"]]

        new_dist = new_total.get("distribution")
        if new_dist:
            e_dist = total_ctx.setdefault("distribution", {"learning":[0,0,0,0], "young":[0,0,0,0], "mature":[0,0,0,0]})
            for ctype, counts in new_dist.items():
                if ctype in e_dist:
                    for i in range(4):
                        if not is_undo:
                            e_dist[ctype][i] += counts[i]
                        else:
                            e_dist[ctype][i] = counts[i]

        # Use the latest streak from delta, but avoid dropping it to 0 if we have an old one
        old_s = e_stats.get("streak", total_ctx.get("streak", 0))
        new_s = d_stats.get("streak", 0)
        e_stats["streak"] = max(old_s, new_s)
        total_ctx["streak"] = e_stats["streak"]

        # Clear expensive derived caches (They will be rebuilt lazily in background)
        total_ctx.pop("oldest_first_reviews", None)
        total_ctx.pop("activity_data", None)
        total_ctx.pop("activity_breakdown", None)
        total_ctx.pop("retention_data", None)
        total_ctx.pop("oldest_first_dates", None)
        total_ctx.pop("desc_dates", None)
        total_ctx["is_dense"] = False

        if "hourly" in new_total:
            e_hourly = total_ctx.setdefault("hourly", {h: {"total": 0, "correct": 0} for h in range(24)})
            n_hourly = new_total["hourly"]
            for h in range(24):
                if n_hourly[h]["total"] > 0:
                    if not is_undo:
                        e_hourly[h]["total"] += n_hourly[h]["total"]
                        e_hourly[h]["correct"] += n_hourly[h]["correct"]
                    else:
                        e_hourly[h]["total"] = n_hourly[h]["total"]
                        e_hourly[h]["correct"] = n_hourly[h]["correct"]

        for k in ["future_due", "future_list", "future_dates"]:
            if k in new_total:
                total_ctx[k] = new_total[k]
        # Only overwrite review_intervals if the delta actually has data, prevents
        # clearing existing cached intervals when delta mode skips the intervals scan.
        new_ivl = new_total.get("review_intervals")
        if new_ivl and new_ivl.get("total", 0) > 0:
            total_ctx["review_intervals"] = new_ivl

        if "fsrs" in total_ctx:
            del total_ctx["fsrs"]

        # Invalidate OTHER ranges (YEAR, MONTH) to force re-slice next time
        keys_to_clear = [k for k in existing_cache if k != Period.TOTAL]
        for k in keys_to_clear:
            del existing_cache[k]




