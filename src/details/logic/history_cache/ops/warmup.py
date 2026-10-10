# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..shared import QTimer, Period, mw, time
from ...logger import log_swallowed


def warmup_selected_decks(cache, deck_ids, cfg=None):
    if cfg is None:
        from .....config import ConfigManager

        cfg = ConfigManager(mw)

    targets = set()
    targets.add(None)

    for did in (deck_ids or []):
        if did is None:
            targets.add(None)
            continue
        targets.add(did)
        for parent_did, leaves in cache.hier_map.items():
            try:
                if did in leaves:
                    targets.add(parent_did)
            except Exception:
                continue

    for did in targets:
        if is_deck_effectively_empty(cache, did):
            continue
        cache.get_context(did, Period.TOTAL, cfg=cfg, allow_sync_check=False)
        cache.get_context(did, Period.YEAR, cfg=cfg, allow_sync_check=False)
        cache.get_context(did, Period.LAST_YEAR, cfg=cfg, allow_sync_check=False)
        cache.get_context(did, Period.MONTH, cfg=cfg, allow_sync_check=False)



def is_deck_effectively_empty(cache, did):
    try:
        deck_cache = cache.cache.get(did, {})
        total_ctx = deck_cache.get(Period.TOTAL, {})
        if not total_ctx:
            return False
        stats = total_ctx.get("stats") or {}
        total_reviews = int(stats.get("total_reviews", 0) or 0)
        return total_reviews == 0
    except Exception:
        return False


def ordered_warmup_decks(cache, priority_deck_ids=None):
    all_decks = list(cache.cache.keys())
    seen = set()
    ordered = []

    def _push(did):
        if did in seen:
            return
        seen.add(did)
        if did in cache.cache:
            ordered.append(did)

    _push(None)

    for did in (priority_deck_ids or []):
        _push(did)
        if did is None:
            continue
        for parent_did, leaves in cache.hier_map.items():
            try:
                if did in leaves:
                    _push(parent_did)
            except Exception:
                continue

    for did in all_decks:
        _push(did)

    return ordered


def schedule_deferred_full_warmup(cache, delay_ms=2000, batch_size=24, budget_ms=10, priority_deck_ids=None):
    try:
        cache._deferred_warmup_priority = list(priority_deck_ids or [])
        if cache._deferred_warmup_timer is None:
            cache._deferred_warmup_timer = QTimer(cache.signals)
            cache._deferred_warmup_timer.setSingleShot(True)
            cache._deferred_warmup_timer.timeout.connect(
                lambda: run_deferred_full_warmup(
                    cache,
                    batch_size=batch_size,
                    budget_ms=budget_ms,
                    priority_deck_ids=cache._deferred_warmup_priority,
                )
            )
        else:
            try:
                cache._deferred_warmup_timer.timeout.disconnect()
            except Exception:
                log_swallowed()
            cache._deferred_warmup_timer.timeout.connect(
                lambda: run_deferred_full_warmup(
                    cache,
                    batch_size=batch_size,
                    budget_ms=budget_ms,
                    priority_deck_ids=cache._deferred_warmup_priority,
                )
            )
        cache._deferred_warmup_timer.start(max(0, int(delay_ms)))
    except Exception as e:
        cache._log(f"schedule_deferred_full_warmup failed: {e}")


def run_deferred_full_warmup(cache, batch_size=24, budget_ms=10, priority_deck_ids=None):
    if cache._deferred_warmup_in_progress:
        return
    cache._deferred_warmup_in_progress = True

    decks = ordered_warmup_decks(cache, priority_deck_ids=priority_deck_ids)
    if not decks:
        cache._deferred_warmup_in_progress = False
        return

    from .....config import ConfigManager

    cfg = ConfigManager(mw)
    total = len(decks)

    def _run_batch(start_idx):
        if start_idx >= total:
            cache._deferred_warmup_in_progress = False
            return

        def _worker():
            processed = 0
            idx = start_idx
            t0 = time.perf_counter()
            while idx < total and processed < batch_size:
                if ((time.perf_counter() - t0) * 1000.0) >= float(budget_ms):
                    break
                did = decks[idx]
                idx += 1
                if is_deck_effectively_empty(cache, did):
                    processed += 1
                    continue
                cache.get_context(did, Period.TOTAL, cfg=cfg, allow_sync_check=False)
                cache.get_context(did, Period.YEAR, cfg=cfg, allow_sync_check=False)
                cache.get_context(did, Period.LAST_YEAR, cfg=cfg, allow_sync_check=False)
                cache.get_context(did, Period.MONTH, cfg=cfg, allow_sync_check=False)
                processed += 1
            return idx

        def _on_done(future):
            try:
                next_idx = int(future.result() or total)
            except Exception:
                next_idx = total
            QTimer.singleShot(60, lambda: _run_batch(next_idx))

        mw.taskman.run_in_background(_worker, on_done=_on_done)

    _run_batch(0)

