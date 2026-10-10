# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..shared import Period, log_info, mw, time
from ...history_provider import HistoryProvider
from ...logger import log_swallowed


def on_profile_switch(cache, cache_cls, *args, **kwargs):
    """Reset in-memory state on profile switch to make sure we load the correct cache."""
    try:
        profile_name = mw.pm.name if (hasattr(mw, "pm") and mw.pm) else "Unknown"
    except Exception:
        profile_name = "Unknown"


    # collection_did_load and profile_did_open both fire when a profile opens: reset once per collection.
    if getattr(cache, "_reset_col", None) is mw.col and mw.col is not None and not cache.is_initialized:
        return

    same_profile_unchanged = profile_name == getattr(cache, "_last_profile", None) and cache.is_initialized
    if same_profile_unchanged:
        # A backup restore (or any external replacement of the collection) reopens the
        # same profile with different content: only skip the reset if the DB is unchanged.
        try:
            from .refresh_monitoring import capture_db_fingerprint
            prev_fp = getattr(cache, "_last_db_fingerprint", None)
            curr_fp = capture_db_fingerprint(cache)
            if prev_fp is None or curr_fp is None or curr_fp != prev_fp:
                same_profile_unchanged = False
                cache._log("Profile reopened with different collection content. Resetting cache.")
        except Exception:
            same_profile_unchanged = False
    if same_profile_unchanged:
        cache._log(f"Profile open: {profile_name} (same profile, skipping reset).")
        return

    cache._last_profile = profile_name
    cache._reset_col = mw.col
    cache._log(f"Profile switch detected: {profile_name}. Resetting cache.")

    cache.cache = {}
    cache.hier_map = {}
    cache.is_initialized = False
    cache.last_max_rev_id = 0
    cache.last_max_card_id = 0
    cache.last_logical_date = None
    cache._is_initializing = False
    cache._init_callbacks = []
    cache._init_deferred_hook_installed = False
    cache._deferred_warmup_priority = []
    cache._hier_cache_data = None
    cache._hier_cache_count = 0
    cache._hier_cache_time = 0.0
    cache._hier_cache_invalidated = False
    cache._hier_prewarm_scheduled = False

    try:
        if hasattr(HistoryProvider, "_session_deleted_count"):
            delattr(HistoryProvider, "_session_deleted_count")
    except Exception:
        log_swallowed()

    try:
        from ....widgets.pinned.widget_factory.utils import PinnedDataManager, invalidate_max_ids_cache

        PinnedDataManager.clear()
        invalidate_max_ids_cache()
    except Exception:
        log_swallowed()

    cache_cls.init_async()


def init_async(cache_cls, callback=None):

    instance = cache_cls()
    if callback:
        with instance._lock:
            instance._init_callbacks.append(callback)

    if mw.col is None:
        from aqt import gui_hooks

        with instance._lock:
            if instance._init_deferred_hook_installed:
                return
            instance._init_deferred_hook_installed = True

        def _deferred_init(*args, **kwargs):
            try:
                gui_hooks.profile_did_open.remove(_deferred_init)
            except ValueError:
                pass
            with instance._lock:
                instance._init_deferred_hook_installed = False
            if mw.col is not None:
                cache_cls.init_async()

        gui_hooks.profile_did_open.append(_deferred_init)
        return

    with instance._lock:
        if instance._is_initializing:
            return


    if instance.is_initialized:
        callbacks = instance._pop_init_callbacks()
        done_cb = (lambda: cache_cls._run_callbacks(callbacks)) if callbacks else None
        instance.refresh_incremental(done_cb)
        return

    with instance._lock:
        if instance._is_initializing:
            return
        instance._is_initializing = True

    if instance._load_from_disk():
        instance.is_initialized = True
        try:
            instance._last_profile = mw.pm.name if (hasattr(mw, "pm") and mw.pm) else None
        except Exception:
            log_swallowed()
        with instance._lock:
            instance._is_initializing = False
        instance._schedule_hierarchy_prewarm(delay_ms=150)
        mw.taskman.run_in_background(instance._prewarm_session_deleted_count)
        # The file on disk may be behind the collection (other device, add-on disabled,
        # Anki closed mid-save): check soon after startup, then periodically.
        instance.schedule_background_checks()
        callbacks = instance._pop_init_callbacks()
        done_cb = (lambda: cache_cls._run_callbacks(callbacks)) if callbacks else None
        instance.refresh_incremental(done_cb)
        return

    start_time = time.time()
    log_info("Cache not found on disk. Starting full build from DB...", tag="CACHE")

    def worker():
        from .....config import ConfigManager

        cfg = ConfigManager(mw)
        return cache_cls._populate_full_cache(cfg, Period.TOTAL)

    def on_done(future):
        try:
            data_map, hier_map = future.result()
            instance.cache.update(data_map)
            instance.hier_map = hier_map
            instance.is_initialized = True
            instance.last_max_rev_id = mw.col.db.scalar("select max(id) from revlog") or 0
            instance.last_max_card_id = mw.col.db.scalar("select max(id) from cards") or 0
            elapsed = time.time() - start_time
            total_reviews = sum(
                ctx.get("stats", {}).get("total_reviews", 0)
                for did_ctxs in instance.cache.values()
                for rng, ctx in did_ctxs.items()
                if rng == -1
            )
            log_info(
                f"Full cache built in {elapsed:.2f}s ({instance.last_max_rev_id} max rev_id, ~{total_reviews} reviews)",
                tag="CACHE",
            )

            instance.schedule_deferred_full_warmup(
                delay_ms=1500,
                batch_size=24,
                budget_ms=10,
                priority_deck_ids=[None],
            )
            instance.schedule_background_checks()
            instance._schedule_hierarchy_prewarm(delay_ms=150)
            mw.taskman.run_in_background(instance._prewarm_session_deleted_count)

            has_fsrs = False
            for did, ctxs in instance.cache.items():
                if Period.TOTAL in ctxs and "fsrs" in ctxs[Period.TOTAL]:
                    has_fsrs = True
                    break

            if not has_fsrs:
                mw.taskman.run_in_background(
                    lambda: cache_cls._populate_fsrs_cache(instance.cache),
                    on_done=lambda f: instance._apply_fsrs_cache(f),
                )
            else:
                instance._save_to_disk()

            callbacks = instance._pop_init_callbacks()
            cache_cls._run_callbacks(callbacks)
        except Exception as e:
            import traceback

            instance._log(f"init_async failed: {e}\n{traceback.format_exc()}")
            callbacks = instance._pop_init_callbacks()
            cache_cls._run_callbacks(callbacks)
        finally:
            with instance._lock:
                instance._is_initializing = False

    mw.taskman.run_in_background(worker, on_done=on_done)

