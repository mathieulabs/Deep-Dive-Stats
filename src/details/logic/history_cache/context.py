# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .shared import Config, Period, datetime, log_debug, mw, timedelta
from .ops.context_helpers import (
    bisect_desc,
    compute_slice_bounds,
    resolve_cache_key,
    resolve_lookup_id,
)
from ..data.transforms.activity_series import build_activity_series, build_breakdown_rows
from ..data.transforms.retention_series import build_retention_series
from ..logger import log_error
from ..logger import log_swallowed


def _hourly_from_days(days):
    """Sum per-day hourly histograms. Returns None if any reviewed day lacks
    one (old cache format), so the caller falls back to the SQL path."""
    out = {h: {"total": 0, "correct": 0} for h in range(24)}
    for day in days:
        if not day.get("reviews"):
            continue
        day_h = day.get("hourly")
        if not day_h:
            return None
        for h, hv in day_h.items():
            slot = out.get(h)
            if slot is None:
                return None
            slot["total"] += hv.get("total", 0)
            slot["correct"] += hv.get("correct", 0)
    return out


class ContextMixin:
    @staticmethod
    def get_context(deck_id, range_type, cfg=None, custom_days=7, custom_type="relative", start_date_str="", end_date_str="", allow_sync_check=True, allow_slow_ops=True):
        if deck_id in [0, "0"]:
            deck_id = None

        instance = GlobalHistoryCache()
        thread_name = None
        try:
            import threading
            thread_name = threading.current_thread().name
        except Exception:
            thread_name = None
        if allow_sync_check and thread_name and thread_name.startswith("ThreadPoolExecutor"):
            allow_sync_check = False
        if allow_sync_check:
            instance._check_incremental_update()

        # Parent decks are stored by string name in cache.
        lookup_id = resolve_lookup_id(instance, deck_id, cfg=cfg)

        deck_cache = instance.cache.get(lookup_id, {})

        cache_key = resolve_cache_key(
            range_type,
            custom_days=custom_days,
            custom_type=custom_type,
            start_date_str=start_date_str,
            end_date_str=end_date_str,
        )

        ctx = deck_cache.get(cache_key)
        # Charts need the TOTAL context dense to draw gaps; a sparse cached one is not reused.
        if ctx and ctx.get("is_dense", True):
            return ctx

        # Non-blocking mode: return early unless the range is an exact match
        if not allow_slow_ops:
            return None

        total_ctx = deck_cache.get(Period.TOTAL)
        if not total_ctx:
            log_debug(f"[CACHE] TOTAL cache MISS for deck {deck_id} - cannot slice {range_type}", tag="CACHE")
            return None

        log_debug(f"[CACHE] Attempting slice from TOTAL for {deck_id} / {range_type}", tag="CACHE")
        # Slice from TOTAL for any requested range so charts stay consistent
        try:
            # Build heavy fields if missing (background threads only)
            if not total_ctx.get("heavy_built", False) and not total_ctx.get("is_dense", True):
                instance._rebuild_heavy_fields(total_ctx)
            from ..data.core.time_utils import get_time_range_ms
            if cfg is None:
                from ....config import ConfigManager
                cfg = ConfigManager(mw)

            week_start = cfg.config.get(Config.WEEK_START, 0)

            start_ms, end_ms, _, _ = get_time_range_ms(
                range_type, week_start=week_start, custom_days=custom_days,
                custom_type=custom_type, start_date_str=start_date_str, end_date_str=end_date_str
            )

            from ....utils import rollover_hour
            off_h = rollover_hour()

            lb_date, ub_date = compute_slice_bounds(start_ms, end_ms, off_h)

            full_history = total_ctx.get("reviews", [])
            n = len(full_history)
            if n == 0:
                log_debug(f"[CACHE] Empty reviews in TOTAL for {deck_id}", tag="CACHE")
                return None

            desc_dates = total_ctx.get("desc_dates")
            if desc_dates is None:
                # In a non-blocking context (e.g. main thread during render) abort rather than build O(N) lists, so PinnedDataManager warmup stays at 0ms.
                if not allow_slow_ops:
                    log_debug(f"[CACHE] Aborting O(N) date building for {deck_id} (non-blocking)", tag="CACHE")
                    return None

                desc_dates = [h["logical_date"] for h in full_history]
                total_ctx["desc_dates"] = desc_dates

            # If all dates > ub_date, returns n (empty slice)
            start_idx = bisect_desc(desc_dates, ub_date, 0, n)

            # Find end_idx: the first element strictly smaller than lb_date, so entries equal to lb_date are included.

            lo, hi = start_idx, n
            while lo < hi:
                mid = (lo + hi) // 2
                if desc_dates[mid] >= lb_date:
                    lo = mid + 1
                else:
                    hi = mid
            end_idx = lo

            sliced_history = full_history[start_idx:end_idx]
            log_debug(f"[CACHE] Slice successful. History items: {len(sliced_history)} (indices {start_idx}:{end_idx})", tag="CACHE")

            total_rev = 0
            total_time = 0
            total_passed = 0
            rev_young = pass_young = rev_mat = pass_mat = 0
            again_cnt = hard_cnt = good_cnt = easy_cnt = 0
            active_days = set()
            sliced_heatmap = {}

            for h in sliced_history:
                ld = h["logical_date"]
                r = h["reviews"]
                total_rev += r
                total_time += h["time_ms"]
                total_passed += h["passed"]
                rev_young += h["rev_young"]
                pass_young += h["pass_young"]
                rev_mat += h["rev_mat"]
                pass_mat += h["pass_mat"]
                again_cnt += h.get("again", 0)
                hard_cnt += h.get("hard", 0)
                good_cnt += h.get("good", 0)
                easy_cnt += h.get("easy", 0)
                if r > 0: active_days.add(ld)

                # Pre-aggregate stats for O(1) access
                sliced_heatmap[ld] = {
                    "reviews": r, "future": 0, "time_ms": h["time_ms"], "passed": h["passed"],
                    "rev_young": h["rev_young"], "pass_young": h["pass_young"],
                    "rev_mat": h["rev_mat"], "pass_mat": h["pass_mat"],
                    "learn_count": h.get("learn_count", 0),
                    "relearn_count": h.get("relearn_count", 0),
                    "young_count": h.get("young_count", 0),
                    "mature_count": h.get("mature_count", 0),
                    "cram_count": h.get("cram_count", 0)
                }

            fd_o = total_ctx.get("future_due", {})
            fd_dist = fd_o.get("distribution", {})
            if fd_dist:
                today_sched = mw.col.sched.today
                for due_idx, count in fd_dist.items():
                    days_diff = due_idx - today_sched
                    # Only project dates within or near the requested range (a buffer covers wrapping years).
                    if days_diff > -365 and days_diff < 3650:
                        proj_dt = datetime.now() + timedelta(days=days_diff)
                        # Recompute the logical date using the rollover hour
                        if proj_dt.hour < off_h: proj_dt -= timedelta(days=1)
                        proj_str = proj_dt.strftime("%Y-%m-%d")

                        # Only merge if it fits in the lb_date window (ignore upper bound for heatmap)
                        if proj_str >= lb_date:
                            entry = sliced_heatmap.setdefault(proj_str, {
                                "reviews": 0, "future": 0, "time_ms": 0, "passed": 0,
                                "rev_young": 0, "pass_young": 0, "rev_mat": 0, "pass_mat": 0,
                                "learn_count": 0, "relearn_count": 0, "young_count": 0, "mature_count": 0, "cram_count": 0
                            })
                            entry["future"] += count

            # Densify: fill zero-review days, since charts need every day in the range.
            lb_dt = datetime.strptime(lb_date, "%Y-%m-%d").date()
            ub_dt = datetime.strptime(ub_date, "%Y-%m-%d").date()

            # For TOTAL, start from the earliest activity across all fields
            if range_type == Period.TOTAL:
                earliest_dates = []
                if full_history:
                    earliest_dates.append(full_history[-1]["logical_date"])

                if earliest_dates:
                    earliest_known = min(earliest_dates)
                    if earliest_known > "1970-01-01":
                        lb_dt = datetime.strptime(earliest_known, "%Y-%m-%d").date()
                else:
                    lb_dt = ub_dt - timedelta(days=6)

            day_range = (ub_dt - lb_dt).days + 1
            if day_range > 15000: day_range = 15000

            history_lookup = {h["logical_date"]: h for h in sliced_history}

            added_full = total_ctx.get("added", [])
            added_lookup = {a["date"]: a for a in added_full}

            added_lb_dt = lb_dt
            if range_type == Period.TOTAL and added_full:
                try:
                    oldest_added_date = datetime.strptime(added_full[-1]["date"], "%Y-%m-%d").date()
                    added_lb_dt = min(lb_dt, oldest_added_date)
                except Exception:
                    log_swallowed()

            day_range_added = (ub_dt - added_lb_dt).days + 1
            if day_range_added > 18000: day_range_added = 18000

            # Cumulative added cards before added_lb_dt
            start_cum = 0
            search_str_added = added_lb_dt.strftime("%Y-%m-%d")
            a_idx = bisect_desc(total_ctx.get("added_dates", []), search_str_added)
            if 0 <= a_idx < len(added_full):
                if added_full[a_idx]["date"] == search_str_added:
                    if a_idx + 1 < len(added_full):
                        start_cum = added_full[a_idx+1]["cumulative"]
                else:
                    start_cum = added_full[a_idx]["cumulative"]

            densified_reviews = []
            densified_added = []
            months_en = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

            for d_off in range(day_range):
                d_dt = lb_dt + timedelta(days=d_off)
                d_str = d_dt.strftime("%Y-%m-%d")
                pretty = f"{months_en[d_dt.month-1]} {d_dt.day:02d}, {d_dt.year}"

                if d_str in history_lookup:
                    densified_reviews.append(history_lookup[d_str])
                else:
                    densified_reviews.append({
                        "date": d_str, "pretty_date": pretty, "logical_date": d_str,
                        "reviews": 0, "time_ms": 0, "passed": 0, "retention": None,
                        "rev_young": 0, "pass_young": 0, "rev_mat": 0, "pass_mat": 0,
                        "ret_young": None, "ret_mat": None,
                        "learn_count": 0, "relearn_count": 0, "young_count": 0, "mature_count": 0, "cram_count": 0,
                        "learn_time_ms": 0, "relearn_time_ms": 0, "young_time_ms": 0, "mature_time_ms": 0, "cram_time_ms": 0,
                        "again": 0, "hard": 0, "good": 0, "easy": 0
                    })

            curr_cum = start_cum
            for d_off in range(day_range_added):
                d_dt = added_lb_dt + timedelta(days=d_off)
                d_str = d_dt.strftime("%Y-%m-%d")
                pretty = f"{months_en[d_dt.month-1]} {d_dt.day:02d}, {d_dt.year}"

                if d_str in added_lookup:
                    entry = added_lookup[d_str]
                    curr_cum += entry.get("count", 0)
                    dense_entry = entry.copy()
                    dense_entry["cumulative"] = curr_cum
                    densified_added.append(dense_entry)
                else:
                    densified_added.append({
                        "date": d_str, "pretty_date": pretty,
                        "count": 0, "cumulative": curr_cum
                    })

            sliced_dist = {
                "learning": [0,0,0,0], "young": [0,0,0,0], "mature": [0,0,0,0]
            }
            for h in sliced_history:
                for k in ["learning", "young", "mature"]:
                    buttons = h.get(f"{k}_buttons")
                    if buttons:
                        for i in range(4):
                            sliced_dist[k][i] += buttons[i]

            # Build hourly for sliced ranges too so charts keep it after a cache slice refresh. The
            # TOTAL cache already stores per-day hour histograms, so summing the sliced days gives
            # the same answer as rescanning the revlog.
            hourly_ctx = total_ctx.get("hourly") if range_type == Period.TOTAL else None
            if hourly_ctx is None and range_type != Period.CUSTOM:
                hourly_ctx = _hourly_from_days(sliced_history)
            if hourly_ctx is None and range_type != Period.CUSTOM:
                try:
                    from ..metrics.hourly import HourlyDataProvider
                    hourly_ctx = HourlyDataProvider.fetch_data(
                        cfg,
                        deck_id=deck_id,
                        is_deleted=(deck_id == -1),
                        time_span=range_type,
                    )
                except Exception:
                    hourly_ctx = None

            result_ctx = {
                "reviews": densified_reviews[::-1],
                "added": densified_added[::-1],
                "counts": total_ctx.get("counts"),
                "distribution": sliced_dist,
                "heatmap_data": sliced_heatmap,
                "hourly": hourly_ctx,
                "future_due": total_ctx.get("future_due") if range_type == Period.TOTAL else None,
                "review_intervals": total_ctx.get("review_intervals") if range_type == Period.TOTAL else None,
                "fsrs": total_ctx.get("fsrs") or {"stability": {}, "difficulty": {}, "retrievability": {}},
                "stats": {
                    "total_reviews": total_rev, "total_time_ms": total_time, "total_passed": total_passed,
                    "rev_young": rev_young, "pass_young": pass_young, "rev_mat": rev_mat, "pass_mat": pass_mat,
                    "active_days": len(active_days),
                    "retention": (total_passed / total_rev * 100) if total_rev > 0 else 0,
                    "streak": total_ctx.get("stats", {}).get("streak", 0),
                    "again": again_cnt, "hard": hard_cnt, "good": good_cnt, "easy": easy_cnt
                },
                "is_dense": True
            }
            sliced_history = result_ctx["reviews"]

            oldest_first = sliced_history[::-1]
            result_ctx["activity_data"] = build_activity_series(oldest_first)
            result_ctx["activity_breakdown"] = build_breakdown_rows(
                oldest_first,
                count_key_style="plain",
            )
            result_ctx["retention_data"] = build_retention_series(oldest_first, count_default=0)

            deck_cache[cache_key] = result_ctx

            return result_ctx
        except Exception as e:
            log_error(f"Error slicing context: {e}")
            return None





