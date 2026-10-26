# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .shared import Period, log_debug, log_info, mw, time
from ..refresh import queue_ui_callback
from .ops.refresh_monitoring import (
    capture_db_fingerprint,
    check_incremental_update,
    get_hierarchy_context,
    invalidate_hierarchy_context,
    prewarm_session_deleted_count,
    rebuild_heavy_fields,
    schedule_background_checks,
    schedule_hierarchy_prewarm,
    verify_integrity,
)
from .ops.refresh_merge import merge_delta
from ..logger import log_swallowed

class RefreshMixin:
    def _capture_db_fingerprint(self):
        return capture_db_fingerprint(self)

    def _run_priority_background(self, worker, on_done=None):
        executor = getattr(self, "_priority_refresh_executor", None)
        if executor is None:
            mw.taskman.run_in_background(worker, on_done=on_done)
            return

        try:
            future = executor.submit(worker)
        except Exception:
            mw.taskman.run_in_background(worker, on_done=on_done)
            return

        if on_done is None:
            return

        def _done(done_future):
            signal_proxy = getattr(self, "signals", None)
            if signal_proxy is not None and hasattr(signal_proxy, "invoke_on_main"):
                signal_proxy.invoke_on_main.emit(lambda: on_done(done_future))
                return
            queue_ui_callback(
                lambda: on_done(done_future),
                delay_ms=0,
                owner=signal_proxy,
                reason="history_cache.priority_refresh.on_done",
            )

        future.add_done_callback(_done)

    def refresh_card_states(self, callback=None):
        """Light refresh after an operation that only changed card states (suspend, bury,
        reschedule, forget...): the review history is the same, so only the card counts,
        due dates, intervals and FSRS charts are read again, from the cards table.
        A full rebuild here would read the whole revlog for nothing."""
        if not self.is_initialized or self._is_refreshing or getattr(self, "_is_initializing", False):
            self.refresh_incremental(callback=callback, force_full=True)
            return

        def worker():
            from .global_cache import GlobalHistoryCache
            with self._lock:
                GlobalHistoryCache._refresh_snapshot_charts(self.cache, self.hier_map)
            return GlobalHistoryCache._populate_fsrs_cache()

        def on_done(future):
            try:
                future.result()
                self._apply_fsrs_cache(future)
            except Exception:
                log_swallowed()
            self._emit_context_updated_coalesced()
            if callback:
                callback()

        mw.taskman.run_in_background(worker, on_done=on_done)

    def refresh_incremental(self, callback=None, force_full=False, warmup_deck_ids=None, skip_warmup=False, max_rev_hint=None):
        """Fetches and merges ONLY new reviews since last sync.
        If force_full is True, it fetches the entire history (used for undos).
        """
        # Guard reviewer UX: skip opportunistic incremental refreshes while reviewing.
        # The dedicated review-return flow will run its own staged refresh with callback.
        try:
            if getattr(mw, "state", None) == "review" and not callback and not force_full:
                return
        except Exception:
            log_swallowed()
        if not self.is_initialized:
            if callback: callback()
            return

        # During sync or profile transitions the collection can be temporarily unavailable: skip instead of raising on mw.col.db.
        try:
            col = getattr(mw, "col", None)
            if col is None or getattr(col, "db", None) is None:
                if callback:
                    queue_ui_callback(
                        callback,
                        delay_ms=0,
                        owner=getattr(callback, "__self__", None),
                        reason="history_cache.refresh_incremental.skip_no_collection",
                    )
                return
        except Exception:
            if callback:
                queue_ui_callback(
                    callback,
                    delay_ms=0,
                    owner=getattr(callback, "__self__", None),
                    reason="history_cache.refresh_incremental.skip_no_collection_exception",
                )
            return

        _worker_dispatched = False
        _set_refreshing_here = False
        try:
            # One-shot guard used by review-return path. If a racing incremental
            # starts just before phase-B, this prevents warmup contention on UI.
            effective_skip_warmup = bool(skip_warmup or getattr(self, "_skip_next_warmup", False))
            if getattr(self, "_skip_next_warmup", False):
                self._skip_next_warmup = False

            if not hasattr(self, "_queued_callbacks"):
                self._queued_callbacks = []
            if not hasattr(self, "_queued_warmup_targets"):
                self._queued_warmup_targets = set()

            with self._lock:
                if self._is_refreshing:
                    if callback and callback not in self._queued_callbacks:
                        self._queued_callbacks.append(callback)
                    if warmup_deck_ids:
                        for t in warmup_deck_ids:
                            self._queued_warmup_targets.add(t)
                    return

                col = getattr(mw, "col", None)
                if col is None or getattr(col, "db", None) is None:
                    if callback:
                        queue_ui_callback(
                            callback,
                            delay_ms=0,
                            owner=getattr(callback, "__self__", None),
                            reason="history_cache.refresh_incremental.skip_no_collection_locked",
                        )
                    return

                used_rev_hint = bool(max_rev_hint)
                if used_rev_hint and not force_full:
                    # The hint skips the max(id) queries, which hides undo / deck moves / deletions
                    # done while reviewing. Verify with cheap checks before trusting it.
                    try:
                        real_rev = col.db.scalar("select max(id) from revlog") or 0
                        real_card = col.db.scalar("select max(id) from cards") or 0
                        placement = col.db.first("select count(*), sum(id), sum(did) from cards") or (0, 0, 0)
                        placement = tuple(int(v or 0) for v in placement)
                        prev_placement = getattr(self, "_last_placement_fp", None)
                        if real_rev < int(self.last_max_rev_id or 0) or real_card < int(self.last_max_card_id or 0):
                            used_rev_hint = False
                        elif prev_placement is not None and placement != prev_placement:
                            force_full = True
                    except Exception:
                        log_swallowed()
                if used_rev_hint:
                    current_max = max(int(max_rev_hint or 0), int(self.last_max_rev_id or 0))
                    current_max_card = int(self.last_max_card_id or 0)
                else:
                    current_max = col.db.scalar("select max(id) from revlog") or 0
                    current_max_card = col.db.scalar("select max(id) from cards") or 0

                start_rev_id = self.last_max_rev_id
                start_card_id = self.last_max_card_id

                if not used_rev_hint and not force_full and current_max == start_rev_id and current_max_card == start_card_id:
                    # Coalesce bursts of identical no-delta checks (startup/render storms)
                    # to keep logs and main-thread work minimal.
                    now_ts = time.time()
                    no_delta_key = (int(current_max), int(current_max_card), bool(callback))
                    last_no_delta_key = getattr(self, "_last_no_delta_key", None)
                    last_no_delta_ts = float(getattr(self, "_last_no_delta_ts", 0.0) or 0.0)
                    if (
                        not callback
                        and last_no_delta_key == no_delta_key
                        and (now_ts - last_no_delta_ts) < 0.6
                    ):
                        return
                    self._last_no_delta_key = no_delta_key
                    self._last_no_delta_ts = now_ts
                    if callback:
                        queue_ui_callback(
                            callback,
                            delay_ms=0,
                            owner=getattr(callback, "__self__", None),
                            reason="history_cache.refresh_incremental.skip_no_delta",
                        )
                    return

                rev_delta = current_max - start_rev_id
                card_delta = current_max_card - start_card_id
                if force_full:
                    log_info(f"Delta: FULL forced. rev_id: {current_max}, card_id: {current_max_card}", tag="CACHE")
                elif rev_delta != 0 or card_delta != 0:
                    log_debug(f"Delta detected: rev_id +{rev_delta}, card_id +{card_delta}", tag="CACHE")

                is_undo_rev = current_max < start_rev_id and not force_full and not used_rev_hint
                is_undo_card = current_max_card < start_card_id and not force_full
                is_undo = is_undo_rev or is_undo_card
                if is_undo:
                    # The 2-day undo patch only touches decks with recent reviews, so a deck whose
                    # last recent review was undone keeps stale data. Undo is rare: rebuild
                    # everything.
                    force_full = True
                    is_undo = False

                # Focused set of dirty decks for the prioritized post-merge work (warmup,
                # snapshots). The full warmup still runs later in low-priority batches.
                dirty_deck_ids = set()
                should_scan_dirty_decks = not (effective_skip_warmup and callback)
                if not force_full and not is_undo and should_scan_dirty_decks:
                    try:
                        if start_rev_id:
                            for (d,) in col.db.all(
                                f"SELECT DISTINCT (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END) "
                                f"FROM revlog "
                                f"LEFT JOIN cards ON revlog.cid = cards.id "
                                f"WHERE revlog.id > {start_rev_id} AND (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END) IS NOT NULL"
                            ):
                                dirty_deck_ids.add(d)
                        if start_card_id:
                            for (d,) in col.db.all(
                                f"SELECT DISTINCT (CASE WHEN odid > 0 THEN odid ELSE did END) FROM cards "
                                f"WHERE id > {start_card_id} AND did IS NOT NULL"
                            ):
                                dirty_deck_ids.add(d)
                    except Exception:
                        # Best-effort optimization only; never block refresh on this.
                        dirty_deck_ids = set()

                self._is_refreshing = True
                _set_refreshing_here = True
                type_str = "UNDO (2-DAY)" if is_undo else ("FULL" if force_full else "DELTA")
                log_debug(f"refresh_incremental STARTED ({type_str}). Spawning worker...", tag="CACHE")

            # Pre-fetch the hierarchy on the main thread (or from cache) to avoid a 140ms stall in the background
            hier_data = self._get_hierarchy_context()

            def worker():
                from .global_cache import GlobalHistoryCache
                _w_start = time.perf_counter()
                log_debug("Background DB worker STARTED.", tag="CACHE")
                from ....config import ConfigManager
                cfg = ConfigManager(mw)
                resolved_current_max = current_max
                resolved_current_max_card = current_max_card

                if is_undo:
                    cutoff_ms = int((time.time() - 2 * 86400) * 1000)
                    m_id = cutoff_ms
                    mc_id = cutoff_ms
                else:
                    m_id = None if force_full else self.last_max_rev_id
                    mc_id = None if force_full else self.last_max_card_id

                res = GlobalHistoryCache._populate_full_cache(cfg, Period.TOTAL, min_rev_id=m_id, min_card_id=mc_id, include_heavy=not is_undo, hier_context=hier_data)

                if used_rev_hint:
                    resolved_current_max = mw.col.db.scalar("select max(id) from revlog") or 0

                # Compute FSRS data in the same background pass so it is ready when the callback
                # fires. Skip the full scan on review-return paths: the delta is tiny, the cached
                # FSRS data is still valid, and the deferred full warmup 2s later updates it if
                # needed.
                if effective_skip_warmup and not force_full and not is_undo:
                    fsrs_leaf, fsrs_dirty = {}, None
                else:
                    dirty_dids = None  # always full scan for correctness (partial breaks parent aggregates)
                    fsrs_leaf, fsrs_dirty = GlobalHistoryCache._populate_fsrs_cache(dirty_dids=dirty_dids)

                # Small deltas merge here in the background thread. Large ones (over 220
                # decks) merge on the main thread so the priority split in on_done runs first.
                merged_in_worker = False
                (delta_map_local, _) = res
                if not force_full and not is_undo and len(delta_map_local) < 220 and delta_map_local:
                    with self._lock:
                        if self.last_max_rev_id <= start_rev_id:
                            self._merge_delta(delta_map_local, is_undo=False)
                            self.last_max_rev_id = resolved_current_max
                            self.last_max_card_id = resolved_current_max_card
                            merged_in_worker = True

                log_debug(f"Background DB worker FINISHED in {(time.perf_counter()-_w_start)*1000:.1f}ms.", tag="CACHE")
                return res, force_full, is_undo, fsrs_leaf, fsrs_dirty, merged_in_worker, time.perf_counter(), resolved_current_max, resolved_current_max_card

            _callbacks_state = {"done": False}

            def _run_waiting_callbacks():
                waiting = []
                if callback:
                    waiting.append(callback)
                waiting.extend(getattr(self, "_queued_callbacks", []) or [])
                self._queued_callbacks = []
                self._queued_warmup_targets = set()
                for cb in waiting:
                    try:
                        cb()
                    except Exception as cb_err:
                        self._log(f"refresh callback failed: {cb_err}")

            def on_done(future):
                try:
                    try:
                        (delta_map, hier_map), was_full, was_undo, fsrs_leaf, fsrs_dirty, merged_in_worker, worker_finished_at, resolved_current_max, resolved_current_max_card = future.result()
                    except Exception:
                        try:
                            (delta_map, hier_map), was_full, was_undo, fsrs_leaf, fsrs_dirty = future.result()
                            merged_in_worker = False
                            resolved_current_max = current_max
                            resolved_current_max_card = current_max_card
                        except Exception:
                            try:
                                (delta_map, hier_map), was_full, was_undo = future.result()
                                fsrs_leaf, fsrs_dirty = {}, None
                                merged_in_worker = False
                                resolved_current_max = current_max
                                resolved_current_max_card = current_max_card
                            except Exception:
                                raise
                    total_delta_decks = len(delta_map)
                    deferred_delta_map = None
                    skip_merge = False

                    if merged_in_worker:
                        # Merge + ID update already done in background thread. Just update hier_map.
                        self.hier_map = hier_map
                    else:
                        # Review return: merge priority decks (global, active, dirty) immediately and
                        # the remaining decks in the background, to keep the callback fast.
                        queued_priority_targets = list(getattr(self, "_queued_warmup_targets", set()) or [])
                        priority_seed_targets = list(warmup_deck_ids or [])
                        if not priority_seed_targets and queued_priority_targets:
                            priority_seed_targets = queued_priority_targets

                        if (
                            (callback or bool(getattr(self, "_queued_callbacks", [])))
                            and priority_seed_targets
                            and not was_full
                            and not was_undo
                            and total_delta_decks > 220
                        ):
                            priority_targets = {None, "[[TOTAL]]"}
                            priority_targets.update(priority_seed_targets)
                            priority_targets.update(dirty_deck_ids or [])
                            immediate_delta_map = {k: v for k, v in delta_map.items() if k in priority_targets}
                            if immediate_delta_map and len(immediate_delta_map) < total_delta_decks:
                                deferred_delta_map = {k: v for k, v in delta_map.items() if k not in priority_targets}
                                delta_map = immediate_delta_map

                        with self._lock:
                            # A concurrent sync that already moved last_max_rev_id past our starting point makes this delta redundant.
                            if not was_full and not was_undo:
                                if self.last_max_rev_id > start_rev_id:
                                    log_info(f"Redundant refresh job detected (current max {self.last_max_rev_id} > job start {start_rev_id}). Skipping merge.", tag="CACHE")
                                    skip_merge = True

                            if not skip_merge:
                                if was_full and not was_undo:
                                    for did, new_ctx in delta_map.items():
                                        self.cache[did] = new_ctx
                                    # Drop decks the full fetch no longer has (deleted or emptied by moves/deletes), otherwise they keep their old numbers forever.
                                    stale = [k for k in list(self.cache.keys()) if k not in delta_map]
                                    for k in stale:
                                        self.cache.pop(k, None)
                                else:
                                    self._merge_delta(delta_map, is_undo=was_undo)
                            # Update the ids under the same lock as the data, so a background save never
                            # pairs merged data with old ids (which re-merged the delta at next launch).
                            self.last_max_rev_id = resolved_current_max
                            self.last_max_card_id = resolved_current_max_card

                        self.hier_map = hier_map

                    # Run fingerprint in background, it does 3 full table scans and
                    # blocks the main thread for 100ms+ if run synchronously here.
                    def _bg_fingerprint(cache_ref=self):
                        fp = cache_ref._capture_db_fingerprint()
                        cache_ref._last_db_fingerprint = fp
                    mw.taskman.run_in_background(_bg_fingerprint)

                    # Apply FSRS cache only when there is actual data, iterating the full
                    # cache with an empty leaf dict wastes ~5-20ms for nothing.
                    if fsrs_leaf:
                        try:
                            import concurrent.futures
                            _fsrs_fut = concurrent.futures.Future()
                            _fsrs_fut.set_result((fsrs_leaf, fsrs_dirty))
                            self._apply_fsrs_cache(_fsrs_fut)
                        except Exception as _fe:
                            self._log(f"FSRS apply failed: {_fe}")
                    elif (was_full or was_undo) and not skip_merge:
                        # _apply_fsrs_cache is what saves to disk. Without FSRS data (FSRS off) a
                        # repaired cache was never written, and the old file came back at every launch.
                        self._save_to_disk()

                    if not effective_skip_warmup:
                        from ....config import ConfigManager
                        cfg = ConfigManager(mw)
                        # Priority targets: explicit caller targets, truly dirty decks and TOTAL, in a deterministic deduplicated order.
                        priority_targets = []
                        seen_targets = set()
                        for t in (warmup_deck_ids or [None]):
                            if t not in seen_targets:
                                seen_targets.add(t)
                                priority_targets.append(t)
                        for d in dirty_deck_ids:
                            if d not in seen_targets:
                                seen_targets.add(d)
                                priority_targets.append(d)
                        if None not in seen_targets:
                            priority_targets.insert(0, None)

                        if warmup_deck_ids is None:
                            # Never do an immediate full warmup here: it can contend with UI
                            # right after review/deck transitions. Keep immediate work tiny.
                            mw.taskman.run_in_background(lambda: self.warmup_selected_decks(priority_targets, cfg=cfg))
                            self.schedule_deferred_full_warmup(
                                delay_ms=2000,
                                batch_size=24,
                                budget_ms=10,
                                priority_deck_ids=priority_targets,
                            )
                        else:
                            # Priority pass: affected deck(s) first for instant perceived update.
                            mw.taskman.run_in_background(lambda: self.warmup_selected_decks(priority_targets, cfg=cfg))
                            self.schedule_deferred_full_warmup(
                                delay_ms=2000,
                                batch_size=24,
                                budget_ms=10,
                                priority_deck_ids=priority_targets,
                            )

                    def _snap_job():
                        from .global_cache import GlobalHistoryCache
                        _s_start = time.perf_counter()
                        m_val = None if was_full else self.last_max_rev_id
                        snap_dirty = None
                        if not was_full and not was_undo:
                            snap_dirty = list(dirty_deck_ids) if dirty_deck_ids else list(delta_map.keys())
                        GlobalHistoryCache._refresh_snapshot_charts(
                            self.cache,
                            self.hier_map,
                            min_rev_id=m_val,
                            dirty_dids=snap_dirty,
                        )
                        log_debug(f"Snapshot charts refresh completed in {(time.perf_counter()-_s_start)*1000:.1f}ms", tag="CACHE")

                    def _snap_done(fut, was_full_=was_full):
                        try:
                            fut.result()
                            if not was_full_:
                                self._emit_context_updated_coalesced()
                        except Exception as _se:
                            self._log(f"snapshot refresh failed: {_se}")

                    mw.taskman.run_in_background(_snap_job, on_done=_snap_done)

                    _callbacks_state["done"] = True
                    _run_waiting_callbacks()

                    self._emit_context_updated_coalesced()

                    if deferred_delta_map:
                        deferred_payload = deferred_delta_map

                        def _deferred_merge_worker():
                            with self._lock:
                                self._merge_delta(deferred_payload, is_undo=False)
                            return len(deferred_payload)

                        def _deferred_merge_done(fut):
                            try:
                                fut.result()
                                try:
                                    self._pending_partial_widget_refresh = {
                                        "reason": "deferred_merge",
                                        "deck_ids": list(deferred_payload.keys()),
                                    }
                                except Exception:
                                    self._pending_partial_widget_refresh = None
                                self._emit_context_updated_coalesced()
                            except Exception:
                                log_swallowed()

                        mw.taskman.run_in_background(_deferred_merge_worker, on_done=_deferred_merge_done)

                except Exception as e:
                    import traceback
                    self._log(f"refresh_incremental on_done failed: {e}\n{traceback.format_exc()}")
                finally:
                    self._is_refreshing = False
                    if not _callbacks_state["done"]:
                        # The worker or the merge failed (e.g. collection closed during a sync). Run
                        # the callbacks anyway: pinned widgets stay hidden after a review until one
                        # fires.
                        _callbacks_state["done"] = True
                        _run_waiting_callbacks()

            use_priority_worker = bool(effective_skip_warmup and callback and not force_full)
            if use_priority_worker:
                self._run_priority_background(worker, on_done=on_done)
            else:
                mw.taskman.run_in_background(worker, on_done=on_done)
            _worker_dispatched = True

        except Exception as e:
            import traceback
            self._log(f"GlobalHistoryCache refresh_incremental worker failed: {e}\n{traceback.format_exc()}")
            if not _worker_dispatched:
                # Failed before the worker started (e.g. no collection while building the deck
                # hierarchy). Leaving _is_refreshing set would queue every later callback
                # forever.
                if _set_refreshing_here:
                    self._is_refreshing = False
                waiting = []
                if callback:
                    waiting.append(callback)
                if _set_refreshing_here:
                    waiting.extend(getattr(self, "_queued_callbacks", []) or [])
                    self._queued_callbacks = []
                for cb in waiting:
                    queue_ui_callback(
                        cb,
                        delay_ms=0,
                        owner=getattr(cb, "__self__", None),
                        reason="history_cache.refresh_incremental.outer_error",
                    )

    def verify_integrity(self, callback=None):
        return verify_integrity(self, callback=callback)

    def schedule_background_checks(self):
        return schedule_background_checks(self)

    def _merge_delta(self, delta_map, is_undo=False):
        return merge_delta(self, delta_map, is_undo=is_undo)

    def _check_incremental_update(self, force_fingerprint=False):
        return check_incremental_update(self, force_fingerprint=force_fingerprint)

    def _get_hierarchy_context(self):
        return get_hierarchy_context(self)

    def _invalidate_hierarchy_context(self, reason="unknown"):
        return invalidate_hierarchy_context(self, reason=reason)

    def _schedule_hierarchy_prewarm(self, delay_ms=150):
        return schedule_hierarchy_prewarm(self, delay_ms=delay_ms)

    def _prewarm_session_deleted_count(self):
        return prewarm_session_deleted_count()

    def _rebuild_heavy_fields(self, ctx):
        return rebuild_heavy_fields(ctx)



