# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .shared import (
    Period,
    log_debug,
    mw,
)
from .ops.population_full import populate_full_cache as populate_full_cache_impl

# Bumped each time the card-state snapshots (counts, future due, intervals,
# hourly) are recomputed. They change without new max ids (suspend, bury,
# forget...), so widgets key their refresh on this too.
_SNAPSHOT_VERSION = [0]


def snapshot_version():
    return _SNAPSHOT_VERSION[0]


class PopulationMixin:
    @staticmethod
    def _populate_full_cache(cfg, range_type, min_rev_id=None, min_card_id=None, include_heavy=True, hier_context=None):
        return populate_full_cache_impl(
            cfg,
            range_type,
            min_rev_id=min_rev_id,
            min_card_id=min_card_id,
            include_heavy=include_heavy,
            hier_context=hier_context,
        )

    @staticmethod
    def _refresh_snapshot_charts(cache, hier_map, min_rev_id=None, dirty_dids=None):
        """Re-calculate Snapshots (Counts, Hourly, FutureDue, ReviewIntervals) efficiently."""
        all_decks_info = {d.id: d.name for d in mw.col.decks.all_names_and_ids()}
        from .exclusion import deck_targets, excluded_dids
        _excl = excluded_dids()

        def get_targets(did):
            return deck_targets(did, all_decks_info, _excl)

        # TOTAL hourly is the sum of the per-day hourly bins, which the delta merge keeps
        # exact (new days added, touched days summed, undone days replaced), so
        # rebuilding it from the bins cannot miss or double count reviews. A full build
        # (min_rev_id None) already has the right totals.
        try:
            if min_rev_id is not None:
                if dirty_dids:
                    targets = set()
                    for d in dirty_dids:
                        targets |= get_targets(d)
                else:
                    targets = set(cache.keys())
                for tdid in targets:
                    ctx = (cache.get(tdid) or {}).get(Period.TOTAL)
                    if not isinstance(ctx, dict):
                        continue
                    h_tot = {h: {"total": 0, "correct": 0} for h in range(24)}
                    for day in ctx.get("reviews") or []:
                        day_h = day.get("hourly") if isinstance(day, dict) else None
                        if not day_h:
                            continue
                        for h, hv in day_h.items():
                            try:
                                hi = int(h)
                            except Exception:
                                continue
                            if 0 <= hi < 24:
                                h_tot[hi]["total"] += hv.get("total", 0)
                                h_tot[hi]["correct"] += hv.get("correct", 0)
                    ctx["hourly"] = h_tot
        except Exception as e:
            log_debug(f"Hourly snapshot refresh failed: {e}", tag="CACHE")

        # Recomputed from the cards table for every deck (cheap grouped SQL), so that
        # suspend / bury / forget / move / answer / undo can never leave stale values.
        try:
            PopulationMixin._recompute_card_snapshots(cache, get_targets)
        except Exception as e:
            log_debug(f"Card snapshot refresh failed: {e}", tag="CACHE")
        _SNAPSHOT_VERSION[0] += 1

    @staticmethod
    def _recompute_card_snapshots(cache, get_targets):
        status_sql = (
            "CASE WHEN queue = -1 THEN 'suspended' WHEN queue < -1 THEN 'buried' "
            "WHEN type = 0 THEN 'new' WHEN type = 1 THEN 'learn' WHEN type = 3 THEN 'relearn' "
            "WHEN type = 2 AND ivl < 21 THEN 'young' WHEN type = 2 AND ivl >= 21 THEN 'mature' "
            "ELSE 'other' END"
        )
        rows_counts = mw.col.db.all(f"SELECT COALESCE((CASE WHEN odid > 0 THEN odid ELSE did END), -1), {status_sql}, COUNT(id) FROM cards GROUP BY 1, 2")
        # The cards of Future Due (counted as in Anki's graph), by Anki due day.
        from ..metrics.future_due import due_day_sql

        fd_day, fd_cond = due_day_sql()
        rows_future = mw.col.db.all(
            f"SELECT COALESCE((CASE WHEN odid > 0 THEN odid ELSE did END), -1), {int(mw.col.sched.today)} + {fd_day}, COUNT(*) "
            f"FROM cards AS cards WHERE {fd_cond} GROUP BY 1, 2")
        from ..metrics.review_intervals import INTERVAL_CARDS_COND

        rows_ivl = mw.col.db.all(
            "SELECT COALESCE((CASE WHEN odid > 0 THEN odid ELSE did END), -1), ivl, COUNT(*) "
            f"FROM cards AS cards WHERE {INTERVAL_CARDS_COND} GROUP BY 1, 2")

        count_keys = ("new", "learn", "relearn", "young", "mature", "buried", "suspended")
        aggs = {}

        def agg_for(t):
            a = aggs.get(t)
            if a is None:
                a = aggs[t] = {"counts": {k: 0 for k in count_keys}, "future": {}, "ivl": {}}
            return a

        for did, status, cnt in rows_counts:
            if status in count_keys:
                for t in get_targets(did):
                    agg_for(t)["counts"][status] += cnt
        for did, due, cnt in rows_future:
            for t in get_targets(did):
                d = agg_for(t)["future"]
                d[due] = d.get(due, 0) + cnt
        for did, ivl, cnt in rows_ivl:
            for t in get_targets(did):
                d = agg_for(t)["ivl"]
                d[ivl] = d.get(ivl, 0) + cnt

        def percentiles(dist):
            total = sum(dist.values())
            p50, p95 = 31, 365
            if total > 0:
                cur = 0
                f50 = f95 = False
                for ivl, c in sorted(dist.items()):
                    cur += c
                    if not f50 and cur >= total * 0.5:
                        p50, f50 = ivl, True
                    if not f95 and cur >= total * 0.95:
                        p95, f95 = ivl, True
                    if f50 and f95:
                        break
            return total, p50, p95

        empty = {"counts": {k: 0 for k in count_keys}, "future": {}, "ivl": {}}
        try:
            from datetime import datetime, timedelta
            from ....utils import rollover_hour

            hm_today = int(mw.col.sched.today or 0)
            hm_off_h = rollover_hour()
            hm_now = datetime.now()
        except Exception:
            hm_today = None

        def reproject_heatmap_future(ctx, fd_dist):
            # Sliced contexts carry heatmap cells whose "future" counts came from the old
            # future-due snapshot. Project the new one into new entry dicts, swapped in at
            # once (widgets may hold the old ones).
            hm = ctx.get("heatmap_data")
            if hm_today is None or not isinstance(hm, dict) or not hm:
                return
            new_hm = {}
            for k, v in hm.items():
                if isinstance(v, dict):
                    e = dict(v)
                    e["future"] = 0
                    new_hm[k] = e
                else:
                    new_hm[k] = v
            lb_date = min(new_hm.keys())
            for due_idx, count in fd_dist.items():
                try:
                    days_diff = int(due_idx) - hm_today
                except Exception:
                    continue
                if not (-365 < days_diff < 3650):
                    continue
                proj_dt = hm_now + timedelta(days=days_diff)
                if proj_dt.hour < hm_off_h:
                    proj_dt -= timedelta(days=1)
                proj_str = proj_dt.strftime("%Y-%m-%d")
                if proj_str < lb_date:
                    continue
                entry = new_hm.get(proj_str)
                if not isinstance(entry, dict):
                    entry = {
                        "reviews": 0, "future": 0, "time_ms": 0, "passed": 0,
                        "rev_young": 0, "pass_young": 0, "rev_mat": 0, "pass_mat": 0,
                        "learn_count": 0, "relearn_count": 0, "young_count": 0, "mature_count": 0, "cram_count": 0,
                    }
                    new_hm[proj_str] = entry
                entry["future"] += count
            ctx["heatmap_data"] = new_hm

        for tdid in list(cache.keys()):
            a = aggs.get(tdid, empty)
            for ctx in list(cache[tdid].values()):
                if not isinstance(ctx, dict):
                    continue
                old = ctx.get("counts") or {}
                new_counts = dict(a["counts"])
                new_counts["deleted"] = old.get("deleted", 0)
                new_counts["total"] = sum(new_counts.values())
                fd = dict(a["future"])
                fd_total = sum(fd.values())
                itotal, p50, p95 = percentiles(a["ivl"])
                ri = dict(ctx.get("review_intervals") or {})
                ri.update({"distribution": dict(a["ivl"]), "total": itotal, "p50": p50, "p95": p95})
                ctx["counts"] = new_counts
                ctx["future_due"] = {
                    "distribution": fd, "total": fd_total,
                    "average": fd_total / max(1, 365), "tomorrow": fd.get(1, 0), "max_days": 3650,
                }
                ctx["review_intervals"] = ri
                try:
                    reproject_heatmap_future(ctx, fd)
                except Exception as e:
                    log_debug(f"Heatmap future reprojection failed: {e}", tag="CACHE")

    @staticmethod
    def _populate_fsrs_cache(dirty_dids=None):
        """Deferred worker: decode FSRS memory states for all cards.

        dirty_dids is ignored on purpose. Fetching only dirty decks would give the
        full-rebuild aggregation incomplete data, and parent decks would lose the
        stability data of their clean children. The scan is cheap (cards.data only).
        """
        if not getattr(mw, "col", None): return {}, dirty_dids
        import time as _time

        from ..fsrs_math import FSRS_CARD_COLS, FSRS_CARD_COND, add_memory_state, memory_state

        try:
            # Always scan all cards, partial data would corrupt parent-deck aggregates
            today_fsrs = mw.col.sched.today
            now = int(_time.time())
            raw_fsrs = mw.col.db.all(
                f"SELECT (CASE WHEN odid > 0 THEN odid ELSE did END), {FSRS_CARD_COLS} "
                f"FROM cards AS cards WHERE {FSRS_CARD_COND}")
        except Exception: return {}, dirty_dids

        leaf_fsrs = {}
        for did_, data, due, odue, odid, ivl, queue, ctype in raw_fsrs:
            mem = memory_state(data)
            if mem is None:
                continue
            bk = leaf_fsrs.setdefault(did_, {"stability": {}, "difficulty": {}, "retrievability": {}})
            add_memory_state(bk, mem, due, odue, odid, ivl, queue, ctype, today_fsrs, now)
        return leaf_fsrs, dirty_dids

    def _apply_fsrs_cache(self, future):
        """Main-thread callback: merge the deferred FSRS data into the live cache.

        Always rebuilds fully with hier_map. A delta update is not possible because
        the cache is keyed by deck name, and the FSRS data is small (about 100
        histogram buckets), so a rebuild is fast.
        """
        try:
            leaf_fsrs, dirty_dids = future.result()

            # Always use full rebuild from fresh leaf data via hier_map
            # This is O(decks * ranges) but FSRS data is tiny (100-bucket histograms)
            for tdid in list(self.cache.keys()):
                children = self.hier_map.get(tdid, [tdid])
                agg_s, agg_d, agg_r = {}, {}, {}
                has_any = False
                for cdid in children:
                    fc = leaf_fsrs.get(cdid)
                    if not fc: continue
                    has_any = True
                    for k, v in fc["stability"].items(): agg_s[k] = agg_s.get(k, 0) + v
                    for k, v in fc["difficulty"].items(): agg_d[k] = agg_d.get(k, 0) + v
                    for k, v in fc["retrievability"].items(): agg_r[k] = agg_r.get(k, 0) + v
                if has_any:
                    fsrs_v = {"stability": agg_s, "difficulty": agg_d, "retrievability": agg_r}
                    for r_k in self.cache[tdid]:
                        if isinstance(self.cache[tdid].get(r_k), dict):
                            self.cache[tdid][r_k]["fsrs"] = fsrs_v

            self._save_to_disk()
        except Exception as e:
            self._log(f"_apply_fsrs_cache failed: {e}")



