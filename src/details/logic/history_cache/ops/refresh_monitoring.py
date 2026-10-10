# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..shared import QTimer, Period, datetime, mw, time, timedelta
from ...data.transforms.activity_series import build_activity_series, build_breakdown_rows
from ...data.transforms.retention_series import build_retention_series
from ...refresh import queue_ui_callback
from ...logger import log_swallowed


def invalidate_hierarchy_context(cache, reason="unknown"):

    cache._hier_cache_invalidated = True
    cache._hier_cache_time = 0.0
    cache._hier_cache_count = 0
    cache._hier_cache_data = None


def schedule_hierarchy_prewarm(cache, delay_ms=150):

    if getattr(cache, "_hier_prewarm_scheduled", False):
        return

    cache._hier_prewarm_scheduled = True

    def _run():
        try:
            get_hierarchy_context(cache)
        except Exception:
            log_swallowed()
        finally:
            cache._hier_prewarm_scheduled = False

    queue_ui_callback(
        _run,
        delay_ms=delay_ms,
        owner=cache,
        reason="history_cache.hierarchy_prewarm",
    )


def prewarm_session_deleted_count():
    from ...history_provider import HistoryProvider

    if hasattr(HistoryProvider, "_session_deleted_count"):
        return

    try:
        count = (
            mw.col.db.scalar(
                """
                SELECT COUNT(DISTINCT revlog.cid)
                FROM revlog
                LEFT JOIN cards ON revlog.cid = cards.id
                WHERE cards.id IS NULL
                """
            )
            or 0
        )
        HistoryProvider._session_deleted_count = count
    except Exception:
        log_swallowed()


def capture_db_fingerprint(cache):
    """Cheap DB fingerprint to catch deletes/imports when max(id) is unchanged."""
    try:
        rev_count, rev_sum = mw.col.db.first("SELECT count(*), sum(id) FROM revlog") or (0, 0)
        card_count, card_sum = mw.col.db.first("SELECT count(*), sum(id) FROM cards") or (0, 0)
        did_count = mw.col.db.scalar("SELECT count(DISTINCT did) FROM cards") or 0
        card_state = mw.col.db.first("SELECT sum(did), sum(queue), sum(type), sum(ivl), sum(due), sum(mod) FROM cards") or (0,) * 6
        try:
            cache._last_placement_fp = (int(card_count or 0), int(card_sum or 0), int(card_state[0] or 0))
        except Exception:
            log_swallowed()
        return (
            int(rev_count or 0),
            int(rev_sum or 0),
            int(card_count or 0),
            int(card_sum or 0),
            int(did_count or 0),
            tuple(int(v or 0) for v in card_state),
        )
    except Exception:
        return None


INTEGRITY_INTERVAL_MS = 10 * 60 * 1000
INTEGRITY_FIRST_CHECK_MS = 15 * 1000
INTEGRITY_RETRY_MS = 20 * 1000
INTEGRITY_MAX_RETRIES = 15


def _snapshot_cache_counts(cache):
    """Review counts per key as the cache sees them (call under cache._lock).

    Returns {key: (stats_total_reviews, sum_of_daily_bins)} for the global context
    and each leaf deck. Key -1 is reviews of deleted cards.
    """
    out = {}
    for key, dcache in list(cache.cache.items()):
        if not (key is None or (isinstance(key, int) and not isinstance(key, bool))):
            continue
        if not isinstance(dcache, dict):
            continue
        ctx = dcache.get(Period.TOTAL)
        if not isinstance(ctx, dict):
            out[key] = (0, 0)
            continue
        stats_total = int((ctx.get("stats") or {}).get("total_reviews", 0) or 0)
        bins_total = 0
        for item in ctx.get("reviews") or []:
            try:
                bins_total += int(item.get("reviews", 0) or 0)
            except Exception:
                log_swallowed()
        out[key] = (stats_total, bins_total)
    return out


def _db_review_counts():
    """Per-deck review counts straight from the collection, with the same rules as the
    cache build: home deck of the card, excluded days left out, type < resched, day bins
    up to the end of the logical day. The returned total skips excluded decks, like the
    all-decks context does."""
    from ..shared import get_time_range_ms
    from ..exclusion import excluded_dids
    from .....utils import excluded_days_clause

    _start, end_ms, _, _ = get_time_range_ms(Period.TOTAL, week_start=0)
    id_ms = "(CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END)"
    rows = mw.col.db.all(
        f"""
        SELECT COALESCE((CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END), -1), COUNT(*)
        FROM revlog LEFT JOIN cards ON revlog.cid = cards.id
        WHERE revlog.type < 4 AND revlog.id > 0 AND {id_ms} < {int(end_ms)}
        {excluded_days_clause()}
        GROUP BY 1
        """
    )
    per_deck = {int(did): int(cnt or 0) for did, cnt in rows}
    excluded = excluded_dids()
    total = sum(cnt for did, cnt in per_deck.items() if did not in excluded)
    return per_deck, total


def _drop_derived_caches():
    """Forget data copied out of the cache (pinned widget contexts, closed Deep Dive window)."""
    try:
        from ....widgets.pinned.widget_factory.utils import PinnedDataManager, invalidate_max_ids_cache

        PinnedDataManager.clear()
        invalidate_max_ids_cache()
    except Exception:
        log_swallowed()
    try:
        from .....startup import _discard_parked_dialog

        _discard_parked_dialog()
    except Exception:
        log_swallowed()


def _retry_verify_later(cache, callback, reason):

    retries = int(getattr(cache, "_integrity_retry_count", 0) or 0)
    if retries >= INTEGRITY_MAX_RETRIES:
        cache._integrity_retry_count = 0
        if callback:
            callback()
        return
    cache._integrity_retry_count = retries + 1
    queue_ui_callback(
        lambda: cache.verify_integrity(callback=callback),
        delay_ms=INTEGRITY_RETRY_MS,
        owner=cache,
        reason="history_cache.verify_integrity_retry",
    )


def verify_integrity(cache, callback=None):
    """Compare the cache with the collection and repair it on mismatch.

    Runs in a background thread and checks:
    - total review count and per-deck review counts (synced older reviews, deleted
      reviews, moved cards, a cache saved mid-merge);
    - each context's stats against the sum of its daily bins;
    - a fingerprint of the revlog and cards tables.

    Reviews that are only waiting to be merged trigger a normal incremental
    refresh. A real mismatch triggers a full rebuild, and one that survives a
    rebuild unchanged is not retried in a loop.
    """

    if not cache.is_initialized:
        if callback:
            callback()
        return

    # Never check while something is changing the cache or the collection is busy: retry a bit later.
    busy_reason = None
    if cache._is_refreshing:
        busy_reason = "refreshing"
    elif getattr(cache, "_is_initializing", False):
        busy_reason = "initializing"
    elif getattr(mw, "col", None) is None:
        busy_reason = "no_collection"
    elif getattr(mw, "state", None) == "review":
        busy_reason = "review_state"
    if busy_reason:
        _retry_verify_later(cache, callback, busy_reason)
        return
    cache._integrity_retry_count = 0

    if getattr(cache, "_integrity_running", False):
        if callback:
            callback()
        return
    cache._integrity_running = True
    cache._log("Integrity check started...", level="DEBUG")

    def worker():
        with cache._lock:
            cached = _snapshot_cache_counts(cache)
            cache_max_rev = int(cache.last_max_rev_id or 0)
            cache_max_card = int(cache.last_max_card_id or 0)
        db_per_deck, db_total = _db_review_counts()
        db_max_rev = int(mw.col.db.scalar("select max(id) from revlog") or 0)
        db_max_card = int(mw.col.db.scalar("select max(id) from cards") or 0)
        fp = capture_db_fingerprint(cache)

        problems = []
        if None not in cached:
            if db_total > 0:
                problems.append("global_context_missing")
        else:
            stats_total, bins_total = cached[None]
            if stats_total != db_total:
                problems.append(f"total {stats_total} != db {db_total}")
            if bins_total != stats_total:
                problems.append(f"global bins {bins_total} != stats {stats_total}")

        for did, db_count in db_per_deck.items():
            stats_total, bins_total = cached.get(did, (0, 0))
            if stats_total != db_count:
                problems.append(f"deck {did}: {stats_total} != db {db_count}")
            elif bins_total != stats_total:
                problems.append(f"deck {did}: bins {bins_total} != stats {stats_total}")
        for did, (stats_total, _bins) in cached.items():
            if did is None or did in db_per_deck:
                continue
            if stats_total:
                problems.append(f"deck {did}: {stats_total} cached, none in db")

        return {
            "problems": problems,
            "db_total": db_total,
            "db_ahead": db_max_rev > cache_max_rev or db_max_card > cache_max_card,
            "fingerprint": fp,
        }

    def on_done(future):
        cache._integrity_running = False
        try:
            res = future.result()
        except Exception as e:
            cache._log(f"Integrity check could not run: {e}")
            if callback:
                callback()
            return

        try:
            problems = res["problems"]
            curr_fp = res["fingerprint"]
            prev_fp = getattr(cache, "_last_db_fingerprint", None)
            fp_changed = prev_fp is not None and curr_fp is not None and curr_fp != prev_fp
            if prev_fp is None and curr_fp is not None:
                cache._last_db_fingerprint = curr_fp

            if res["db_ahead"] and not getattr(cache, "_integrity_catchup_pending", False):
                # Reviews/cards newer than the cache: not corruption, just not merged yet.
                cache._integrity_catchup_pending = True

                def _after_catch_up():
                    queue_ui_callback(
                        lambda: _finish_catch_up(),
                        delay_ms=1500,
                        owner=cache,
                        reason="history_cache.verify_after_catch_up",
                    )

                def _finish_catch_up():
                    cache._integrity_catchup_pending = False
                    cache.verify_integrity(callback=callback)

                cache.refresh_incremental(callback=_after_catch_up)
                return
            cache._integrity_catchup_pending = False

            if not problems and not fp_changed:
                cache._integrity_last_bad_signature = None
                cache._log("Integrity check completed (OK).", level="DEBUG")
                if callback:
                    callback()
                return

            signature = (res["db_total"], curr_fp, tuple(problems[:20]))
            if signature == getattr(cache, "_integrity_last_bad_signature", None):
                # Same mismatch right after a full rebuild: rebuilding again would loop.
                cache._log(
                    "Integrity mismatch persists after a full rebuild, not rebuilding again: "
                    + "; ".join(problems[:5])
                )
                if callback:
                    callback()
                return
            cache._integrity_last_bad_signature = signature

            reason = "; ".join(problems[:5]) if problems else "collection fingerprint changed"
            if len(problems) > 5:
                reason += f" (+{len(problems) - 5} more)"
            cache._log(f"Integrity mismatch detected ({reason}). Forcing full rebuild.")
            if curr_fp is not None:
                cache._last_db_fingerprint = curr_fp
            _drop_derived_caches()

            def _after_rebuild():
                # Pinned widgets key their contexts on max ids, which a repair does not change.
                # Drop what they fetched during the rebuild so the following context_updated
                # refresh reads the repaired data.
                _drop_derived_caches()
                if callback:
                    callback()

            cache.refresh_incremental(callback=_after_rebuild, force_full=True)
        except Exception as e:
            cache._log(f"verify_integrity check failed: {e}")
            if callback:
                callback()

    try:
        mw.taskman.run_in_background(worker, on_done=on_done)
    except Exception as e:
        cache._integrity_running = False
        cache._log(f"verify_integrity could not start: {e}")
        if callback:
            callback()


def schedule_background_checks(cache):
    """Periodic integrity checks. Safe to call several times (one timer only)."""
    timer = getattr(cache, "_integrity_timer", None)
    if timer is None:
        timer = QTimer(cache.signals)
        timer.timeout.connect(lambda: cache.verify_integrity())
        cache._integrity_timer = timer

    if not getattr(cache, "_integrity_first_check_queued", False):
        cache._integrity_first_check_queued = True

        def _first_check():
            cache._integrity_first_check_queued = False
            cache.verify_integrity()

        queue_ui_callback(
            _first_check,
            delay_ms=INTEGRITY_FIRST_CHECK_MS,
            owner=cache,
            reason="history_cache.verify_integrity_first",
        )

    if not timer.isActive():
        timer.start(INTEGRITY_INTERVAL_MS)


def check_incremental_update(cache, force_fingerprint=False):
    """Cheap check to see if new reviews were added OR removed since last cache."""
    if not cache.is_initialized:
        return

    try:
        if getattr(mw, "state", None) == "review":
            return
    except Exception:
        log_swallowed()

    import threading

    if threading.current_thread() is not threading.main_thread():
        return

    try:
        current_max = mw.col.db.scalar("select max(id) from revlog") or 0
        current_max_card = mw.col.db.scalar("select max(id) from cards") or 0

        from .....utils import rollover_hour

        now_dt = datetime.now()
        if now_dt.hour < rollover_hour():
            now_dt -= timedelta(days=1)
        current_date_str = now_dt.strftime("%Y-%m-%d")

        previous_logical_date = getattr(cache, "last_logical_date", None)
        logical_date_seeded = bool(getattr(cache, "_logical_date_seeded", False))
        day_changed = False
        if logical_date_seeded and previous_logical_date is not None:
            if previous_logical_date != current_date_str:
                day_changed = True

        cache.last_logical_date = current_date_str
        cache._logical_date_seeded = True

        if current_max != cache.last_max_rev_id or current_max_card != cache.last_max_card_id or day_changed:
            if day_changed:
                for did, dcache in cache.cache.items():
                    keys_to_clear = [k for k in dcache if k != Period.TOTAL and k != "is_dense"]
                    for k in keys_to_clear:
                        del dcache[k]
                cache.refresh_incremental(force_full=True)
            else:
                cache.refresh_incremental()
            return

        if force_fingerprint:
            curr_fp = cache._capture_db_fingerprint()
            if curr_fp is not None:
                prev_fp = getattr(cache, "_last_db_fingerprint", None)
                if prev_fp is None:
                    cache._last_db_fingerprint = curr_fp
                    cache.refresh_incremental(force_full=True)
                elif curr_fp != prev_fp:
                    cache._last_db_fingerprint = curr_fp
                    cache.refresh_incremental(force_full=True)
                else:
                    pass
        else:
            pass
    except Exception:
        log_swallowed()


def get_hierarchy_context(cache):
    """Builds or returns a cached hierarchy map. Only called on main thread."""
    cached_data = getattr(cache, "_hier_cache_data", None)
    if cached_data is not None and not getattr(cache, "_hier_cache_invalidated", False):
        return cached_data

    all_decks = mw.col.decks.all_names_and_ids()
    deck_count = len(all_decks)
    all_decks_info = {d.id: d.name for d in all_decks}

    hier_map = {}

    from ..exclusion import excluded_dids, drop_total_targets
    _excl = excluded_dids()

    def get_targets(did):
        t = {did, None, "[[TOTAL]]"}
        name = all_decks_info.get(did)
        if name:
            parts = name.split("::")
            for i in range(1, len(parts)):
                t.add("::".join(parts[:i]))
        return drop_total_targets(t, did, _excl)

    for d in all_decks:
        for t in get_targets(d.id):
            hier_map.setdefault(t, []).append(d.id)

    hier_map[-1] = [-1]

    cache._hier_cache_time = time.time()
    cache._hier_cache_count = deck_count
    cache._hier_cache_invalidated = False
    cache._hier_cache_data = (hier_map, all_decks_info)
    return cache._hier_cache_data


def rebuild_heavy_fields(ctx):
    """Reconstruct expensive O(N) fields (desc_dates/activity_data/etc)."""
    history = ctx.get("reviews", [])
    if not history:
        return

    ctx["desc_dates"] = [h["logical_date"] for h in history]
    oldest_first = history[::-1]
    ctx["oldest_first_dates"] = [h["logical_date"] for h in oldest_first]
    ctx["oldest_first_reviews"] = oldest_first

    ctx["activity_data"] = build_activity_series(oldest_first)
    ctx["activity_breakdown"] = build_breakdown_rows(oldest_first, count_key_style="plain")
    ctx["retention_data"] = build_retention_series(oldest_first, count_default=0)

    ctx["heavy_built"] = True


