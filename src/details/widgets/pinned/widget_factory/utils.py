# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt import mw
from aqt.qt import QColor

from ....ui import Period, ConfigManager
from ...common import create_checkbox, create_radio_group
from ...common.pill_toggles import pill_checkbox_qss, pill_radio_qss
from ...chart_utils.theme import (
    ThemeContext,
    coerce_theme_context,
    get_theme_colors,
    resolve_widget_theme_context,
)
from ....logic.data.transforms.activity_series import (
    build_activity_series,
    build_breakdown_rows,
)
from ....logic.data.transforms.retention_series import build_retention_series
from ....logic.data.context_payloads import (
    get_context_history_payload,
    get_default_history_payload,
)
from ....logic.data.section_fetchers import fetch_section_data
from ....logic import log_debug
from ..context_access import fetch_pinned_context_data, get_pinned_context
from .....qss import set_qss
from ....logic.logger import log_error
from ....logic.logger import log_swallowed

def _theme_ref_for_controls(parent=None):
    # Never guess "details" implicitly from a random widget instance.
    # Use explicit context if present; otherwise default to pinned.
    return resolve_widget_theme_context(parent, default=ThemeContext.PINNED)


def _theme_vars(widget_or_context=None):
    if isinstance(widget_or_context, ThemeContext):
        theme_ref = widget_or_context
    elif isinstance(widget_or_context, str):
        theme_ref = coerce_theme_context(widget_or_context, default=ThemeContext.PINNED)
    else:
        theme_ref = _theme_ref_for_controls(widget_or_context)

    t_colors = get_theme_colors(theme_ref)
    is_dark = bool(t_colors.get("is_dark"))
    text_primary = t_colors.get("text_primary", t_colors.get("text"))
    text_secondary = t_colors.get("text_secondary", t_colors.get("text"))
    bg = t_colors.get("bg")
    border = t_colors.get("border")

    def _hex_or_default(qc, default_hex):
        try:
            return qc.name() if qc is not None else default_hex
        except Exception:
            return default_hex

    text_primary_hex = _hex_or_default(text_primary, "#f4f4f5" if is_dark else "#27272a")
    text_secondary_hex = _hex_or_default(text_secondary, "#a1a1aa" if is_dark else "#52525b")
    border_hex = _hex_or_default(border, "#3f3f46" if is_dark else "#d4d4d8")
    bg_hex = _hex_or_default(bg, "#18181b" if is_dark else "#ffffff")

    # Slightly transparent card background that follows the current theme hue.
    from aqt.qt import QColor
    bg_col = QColor(bg_hex)
    bg_alpha = 150 if is_dark else 215
    bg_card = f"rgba({bg_col.red()}, {bg_col.green()}, {bg_col.blue()}, {bg_alpha})"
        
    return {
        "is_dark": is_dark,
        "text_primary": text_primary_hex,
        "text_secondary": text_secondary_hex,
        "bg_hex": bg_hex,
        "bg_card": bg_card,
        "border": border_hex,
    }

def _apply_checkbox_style(cb):
    """Re-apply theme-aware stylesheet to an existing QCheckBox."""
    theme_ref = _theme_ref_for_controls(cb)
    t_colors = get_theme_colors(theme_ref)
    is_dark = bool(t_colors.get("is_dark"))
    text_col = t_colors.get("text_secondary", t_colors.get("text"))
    accent_col = t_colors.get("accent")
    text_hex = text_col.name() if text_col is not None else ("#a1a1aa" if is_dark else "#71717a")
    if accent_col is not None:
        accent_rgba = f"rgba({accent_col.red()}, {accent_col.green()}, {accent_col.blue()}, 180)"
    else:
        accent_rgba = "rgba(59, 130, 246, 180)"

    try:
        text_override = cb.property("deepdivestats_text_color")
    except Exception:
        text_override = None
    if text_override:
        text_hex = str(text_override)

    try:
        accent_override = cb.property("deepdivestats_accent_rgba")
    except Exception:
        accent_override = None
    if accent_override:
        accent_rgba = str(accent_override)

    chart_ref = getattr(cb, "_deepdivestats_retention_chart_ref", None)
    try:
        series_key = cb.property("deepdivestats_retention_series_key")
    except Exception:
        series_key = None
    from ...charts.retention.series import SERIES_KEYS

    series_key = str(series_key or "").strip().lower()
    if series_key in SERIES_KEYS:
        try:
            from ...charts.retention import RetentionChart

            color_ctx = chart_ref if chart_ref is not None else cb
            c = QColor(RetentionChart._get_series_color(series_key, color_ctx))
            if c.isValid():
                series_rgba = f"rgba({c.red()}, {c.green()}, {c.blue()}, 180)"
                text_hex = series_rgba
                accent_rgba = series_rgba
        except Exception:
            log_swallowed()

    try:
        font_weight_override = cb.property("deepdivestats_font_weight")
    except Exception:
        font_weight_override = None

    try:
        padding_right = cb.property("deepdivestats_padding_right")
    except Exception:
        padding_right = None
    padding_css = ""
    if padding_right is not None and str(padding_right).strip() != "":
        try:
            padding_css = f"padding-right: {int(padding_right)}px;"
        except Exception:
            padding_css = f"padding-right: {str(padding_right)};"

    # Pill toggle (shared with the Deep Dive): no tick box, the pill lights up.
    margin_css = padding_css.replace("padding-right", "margin-right")
    set_qss(cb, pill_checkbox_qss(
        text_hex, accent_rgba, is_dark,
        font_weight=str(font_weight_override or "600"),
        extra_css=margin_css,
    ))


def _apply_radio_style(rb):
    """Re-apply theme-aware stylesheet to an existing QRadioButton."""
    theme_ref = _theme_ref_for_controls(rb)
    t_colors = get_theme_colors(theme_ref)
    is_dark = bool(t_colors.get("is_dark"))
    text_col = t_colors.get("text_secondary", t_colors.get("text"))
    accent_col = t_colors.get("accent")
    color_text = text_col.name() if text_col is not None else ("#a1a1aa" if is_dark else "#71717a")
    if accent_col is not None:
        accent_rgba = f"rgba({accent_col.red()}, {accent_col.green()}, {accent_col.blue()}, 180)"
    else:
        accent_rgba = "rgba(59, 130, 246, 180)"
    # Segmented-control look (shared with the Deep Dive).
    set_qss(rb, pill_radio_qss(color_text, accent_rgba, is_dark))


def _make_checkbox(text, checked=True, parent=None):
    return create_checkbox(text, checked=checked, parent=parent, setup=_apply_checkbox_style)

def _make_radio_group(options, default_idx, callback, parent=None):
    return create_radio_group(
        options,
        default_idx,
        callback,
        parent=parent,
        setup_button=_apply_radio_style,
    )

def _addon_config():
    return ConfigManager(mw)

import time
import threading
_last_max_ids_cache = {"rev_id": 0, "card_id": 0, "time": 0}
_last_incremental_trigger_ts = 0.0


def invalidate_max_ids_cache():
    _last_max_ids_cache["time"] = 0


def refresh_max_ids_cache_now():
    """Force an immediate max-id DB read and update the local cache."""
    try:
        prev_rev = _last_max_ids_cache["rev_id"]
        prev_card = _last_max_ids_cache["card_id"]
        max_rev = mw.col.db.scalar("select max(id) from revlog") or 0
        max_card = mw.col.db.scalar("select max(id) from cards") or 0
        _last_max_ids_cache["rev_id"] = max_rev
        _last_max_ids_cache["card_id"] = max_card
        _last_max_ids_cache["time"] = time.time()
        _maybe_trigger_incremental_refresh(prev_rev, prev_card, max_rev, max_card)
        return max_rev, max_card
    except Exception:
        return _last_max_ids_cache["rev_id"], _last_max_ids_cache["card_id"]

def _get_max_ids(allow_db=True):
    now = time.time()
    if not allow_db or now - _last_max_ids_cache["time"] < 1.0:  # 1s cache or skip DB
        return _last_max_ids_cache["rev_id"], _last_max_ids_cache["card_id"]
    
    try:
        prev_rev = _last_max_ids_cache["rev_id"]
        prev_card = _last_max_ids_cache["card_id"]
        max_rev = mw.col.db.scalar("select max(id) from revlog") or 0
        max_card = mw.col.db.scalar("select max(id) from cards") or 0
        _last_max_ids_cache["rev_id"] = max_rev
        _last_max_ids_cache["card_id"] = max_card
        _last_max_ids_cache["time"] = now
        _maybe_trigger_incremental_refresh(prev_rev, prev_card, max_rev, max_card)
        return max_rev, max_card
    except Exception:
        return _last_max_ids_cache["rev_id"], _last_max_ids_cache["card_id"]


def _maybe_trigger_incremental_refresh(prev_rev, prev_card, max_rev, max_card):
    """When DB ids changed (e.g. card added), trigger a throttled cache delta refresh."""
    if max_rev == prev_rev and max_card == prev_card:
        return
    # Never trigger background cache refresh while user is in reviewer.
    # Review-return path manages its own staged refresh to avoid UI freezes.
    try:
        if getattr(mw, "state", None) == "review":
            return
    except Exception:
        log_swallowed()
    if threading.current_thread() is not threading.main_thread():
        return
    global _last_incremental_trigger_ts
    now = time.time()
    if now - _last_incremental_trigger_ts < 1.5:
        return
    _last_incremental_trigger_ts = now
    try:
        from ....logic.history_cache import GlobalHistoryCache
        ghc = GlobalHistoryCache()
        if ghc.is_initialized and not getattr(ghc, "_is_refreshing", False):
            ghc.refresh_incremental()
    except Exception:
        log_swallowed()

def _merge_contexts(contexts):
    """Merge multiple per-deck cache contexts into a single combined context (pure RAM, no SQL)."""
    if not contexts:
        return None
    if len(contexts) == 1:
        return contexts[0]

    _NUM = (
        "reviews", "time_ms", "passed", "rev_young", "pass_young",
        "rev_mat", "pass_mat", "learn_count", "relearn_count",
        "young_count", "mature_count", "cram_count",
        "learn_time_ms", "relearn_time_ms", "young_time_ms",
        "mature_time_ms", "cram_time_ms", "again", "hard", "good", "easy",
    )

    reviews_by_date = {}
    for ctx in contexts:
        for row in (ctx.get("reviews") or []):
            d = row.get("logical_date") or row.get("date", "")
            if not d:
                continue
            if d not in reviews_by_date:
                reviews_by_date[d] = dict(row)
            else:
                base = reviews_by_date[d]
                for f in _NUM:
                    base[f] = (base.get(f) or 0) + (row.get(f) or 0)
    for row in reviews_by_date.values():
        r = row.get("reviews", 0)
        p = row.get("passed", 0)
        row["retention"] = (p / r * 100) if r > 0 else None
        ry = row.get("rev_young", 0); py = row.get("pass_young", 0)
        row["ret_young"] = (py / ry * 100) if ry > 0 else None
        rm = row.get("rev_mat", 0); pm = row.get("pass_mat", 0)
        row["ret_mat"] = (pm / rm * 100) if rm > 0 else None
    merged_reviews = sorted(reviews_by_date.values(), key=lambda r: r.get("logical_date", ""), reverse=True)

    added_by_date = {}
    for ctx in contexts:
        for row in (ctx.get("added") or []):
            d = row.get("date", "")
            if not d:
                continue
            if d not in added_by_date:
                added_by_date[d] = dict(row)
            else:
                added_by_date[d]["count"] = (added_by_date[d].get("count") or 0) + (row.get("count") or 0)
    cum = 0
    for d in sorted(added_by_date):
        cum += added_by_date[d].get("count", 0)
        added_by_date[d]["cumulative"] = cum
    merged_added = sorted(added_by_date.values(), key=lambda r: r.get("date", ""), reverse=True)

    _STAT_SUMS = ("total_reviews", "total_time_ms", "total_passed",
                  "rev_young", "pass_young", "rev_mat", "pass_mat",
                  "active_days", "again", "hard", "good", "easy")
    ms = {}
    for ctx in contexts:
        for f in _STAT_SUMS:
            ms[f] = ms.get(f, 0) + (ctx.get("stats", {}).get(f) or 0)
    tr = ms.get("total_reviews", 0)
    ms["retention"] = (ms.get("total_passed", 0) / tr * 100) if tr > 0 else 0
    # Streak and active days come from the merged days: a review in one deck on Monday and in
    # another on Tuesday is a 2-day streak, and a day studied in two decks is one active day.
    from ....logic.data.core.streaks import current_streak_from_dates

    active_dates = [r.get("logical_date") or r.get("date", "") for r in merged_reviews if (r.get("reviews") or 0) > 0]
    ms["streak"] = current_streak_from_dates(active_dates)
    ms["active_days"] = len(set(active_dates))

    merged_dist = {"learning": [0, 0, 0, 0], "young": [0, 0, 0, 0], "mature": [0, 0, 0, 0]}
    for ctx in contexts:
        for cat in ("learning", "young", "mature"):
            src = (ctx.get("distribution") or {}).get(cat) or [0, 0, 0, 0]
            for i in range(4):
                merged_dist[cat][i] += src[i] if i < len(src) else 0

    _HM = ("reviews", "future", "time_ms", "passed", "rev_young", "pass_young",
           "rev_mat", "pass_mat", "learn_count", "relearn_count",
           "young_count", "mature_count", "cram_count")
    merged_hm = {}
    for ctx in contexts:
        for d, hrow in (ctx.get("heatmap_data") or {}).items():
            if d not in merged_hm:
                merged_hm[d] = dict(hrow)
            else:
                for f in _HM:
                    merged_hm[d][f] = (merged_hm[d].get(f) or 0) + (hrow.get(f) or 0)

    merged_hourly = {h: {"total": 0, "correct": 0} for h in range(24)}
    for ctx in contexts:
        for h, hv in (ctx.get("hourly") or {}).items():
            merged_hourly[h]["total"] += hv.get("total", 0)
            merged_hourly[h]["correct"] += hv.get("correct", 0)

    merged_counts = None
    for ctx in contexts:
        c = ctx.get("counts")
        if c is None:
            continue
        if merged_counts is None:
            merged_counts = dict(c)
        else:
            for k, v in c.items():
                if isinstance(v, (int, float)):
                    merged_counts[k] = merged_counts.get(k, 0) + v

    import copy
    merged_ivl = None
    for ctx in contexts:
        ivl = ctx.get("review_intervals")
        if not ivl:
            continue
        if merged_ivl is None:
            merged_ivl = copy.deepcopy(ivl)
        else:
            for k, v in ivl.items():
                if isinstance(v, (int, float)):
                    merged_ivl[k] = merged_ivl.get(k, 0) + v
                elif isinstance(v, dict):
                    for kk, vv in v.items():
                        if isinstance(vv, (int, float)):
                            merged_ivl.setdefault(k, {})[kk] = merged_ivl.get(k, {}).get(kk, 0) + vv

    merged_fd = None
    for ctx in contexts:
        fd = ctx.get("future_due")
        if not fd:
            continue
        if merged_fd is None:
            merged_fd = copy.deepcopy(fd)
        else:
            for k, v in (fd.get("distribution") or {}).items():
                if isinstance(v, (int, float)):
                    merged_fd.setdefault("distribution", {})[k] = merged_fd.get("distribution", {}).get(k, 0) + v

    merged_fsrs = {"stability": {}, "difficulty": {}, "retrievability": {}}
    for ctx in contexts:
        for key in ("stability", "difficulty", "retrievability"):
            for bk, bv in ((ctx.get("fsrs") or {}).get(key) or {}).items():
                if isinstance(bv, (int, float)):
                    merged_fsrs[key][bk] = merged_fsrs[key].get(bk, 0) + bv

    oldest_first = merged_reviews[::-1]
    activity_data = build_activity_series(oldest_first)
    activity_breakdown = build_breakdown_rows(oldest_first, count_key_style="plain")
    retention_data = build_retention_series(oldest_first, count_default=0)

    return {
        "reviews": merged_reviews, "added": merged_added,
        "counts": merged_counts, "distribution": merged_dist,
        "heatmap_data": merged_hm, "hourly": merged_hourly,
        "future_due": merged_fd, "review_intervals": merged_ivl,
        "fsrs": merged_fsrs, "stats": ms,
        "activity_data": activity_data, "activity_breakdown": activity_breakdown,
        "retention_data": retention_data,
        "is_dense": True,
    }


def cache_data_version():
    """Which reviews and cards the history cache currently holds.

    Data computed from an older cache must not be reused even when the database
    ids are the same (e.g. reviews from another device merged just after startup).
    """
    try:
        from ....logic.history_cache import GlobalHistoryCache

        cache = GlobalHistoryCache()
        return (
            int(getattr(cache, "last_max_rev_id", 0) or 0),
            int(getattr(cache, "last_max_card_id", 0) or 0),
        )
    except Exception:
        return (0, 0)


class PinnedDataManager:
    _context_cache = {} # (deck_id, range_type, max_rev_id) -> context_dict
    _pending_fetches = {} # (deck_id, range_type, max_rev_id) -> list of callbacks
    _context_cache_version = None

    @staticmethod
    def _drop_contexts_if_cache_changed():
        # Snapshot passes rewrite the cache without new ids: also drop copies made
        # before them (multi-deck merges and sliced contexts hold old snapshot dicts).
        try:
            from ....logic.history_cache.population import snapshot_version

            snap = snapshot_version()
        except Exception:
            snap = None
        version = (cache_data_version(), snap)
        if version != PinnedDataManager._context_cache_version:
            PinnedDataManager._context_cache.clear()
            PinnedDataManager._context_cache_version = version

    @staticmethod
    def _get_multi_deck_context(deck_ids, range_type, cfg=None, custom_days=7, custom_type="relative",
                                start_date_str="", end_date_str="", allow_slow_ops=True):
        """Aggregate per-deck cache contexts for a multi-deck selection (no SQL)."""
        from ....logic.history_cache import GlobalHistoryCache
        numeric_ids = [d for d in deck_ids if isinstance(d, int)]
        if "deleted" in deck_ids:
            numeric_ids.append(-1)
        max_ids = _get_max_ids(allow_db=allow_slow_ops)
        cache_key = (tuple(sorted(numeric_ids)), int(range_type),
                     int(custom_days) if custom_days is not None else 0,
                     custom_type, start_date_str, end_date_str, max_ids)

        ctx = PinnedDataManager._context_cache.get(cache_key)
        if ctx:
            return ctx

        contexts = []
        for did in numeric_ids:
            c = GlobalHistoryCache.get_context(
                did, range_type, cfg=cfg,
                custom_days=custom_days, custom_type=custom_type,
                start_date_str=start_date_str, end_date_str=end_date_str,
                allow_sync_check=False, allow_slow_ops=allow_slow_ops,
            )
            if c:
                contexts.append(c)

        if not contexts:
            return None

        merged = _merge_contexts(contexts)
        if merged:
            PinnedDataManager._context_cache[cache_key] = merged
        return merged

    @staticmethod
    def get_context(deck_id, range_type, cfg=None, custom_days=7, custom_type="relative", start_date_str="", end_date_str="", allow_sync_check=False, allow_slow_ops=True):
        if range_type is None: range_type = Period.TOTAL
        PinnedDataManager._drop_contexts_if_cache_changed()
        if isinstance(deck_id, list):
            return PinnedDataManager._get_multi_deck_context(
                deck_id, range_type, cfg=cfg,
                custom_days=custom_days, custom_type=custom_type,
                start_date_str=start_date_str, end_date_str=end_date_str,
                allow_slow_ops=allow_slow_ops,
            )
        # Keep widget path cache-only (no implicit incremental refresh) while still
        # refreshing max ids from DB when slow ops are allowed, so post-review keys rotate.
        max_ids = _get_max_ids(allow_db=allow_slow_ops)
        
        from ....logic import log_debug
        
        key = (deck_id, int(range_type), int(custom_days) if custom_days is not None else 0, custom_type, start_date_str, end_date_str, max_ids)
        
        ctx = PinnedDataManager._context_cache.get(key)
        if ctx: 
            log_debug(f"[PINNED] Local cache HIT for {deck_id} / {range_type} (custom_days={custom_days})", tag="PINNED")
            return ctx
        
        from ....logic.history_cache import GlobalHistoryCache
        log_debug(f"[PINNED] GlobalHistoryCache.get_context: deck={deck_id}, range={range_type}, allow_slow={allow_slow_ops}", tag="PINNED")
        global_ctx = GlobalHistoryCache.get_context(
            deck_id, range_type, cfg=cfg, 
            custom_days=custom_days, custom_type=custom_type, 
            start_date_str=start_date_str, end_date_str=end_date_str,
            allow_sync_check=False,
            allow_slow_ops=allow_slow_ops
        )
        if global_ctx:
            log_debug(f"[PINNED] GlobalHistoryCache HIT for {deck_id} / {range_type}", tag="PINNED")
            if deck_id == -1:
                from ....logic.history_provider.deleted_states import enrich_deleted_context
                global_ctx = enrich_deleted_context(global_ctx)
            PinnedDataManager._context_cache[key] = global_ctx
            return global_ctx
            
        log_debug(f"[PINNED] get_context MISS for {deck_id} / {range_type} (allow_slow={allow_slow_ops})", tag="PINNED")
        return None

    @staticmethod
    def clear():
        PinnedDataManager._context_cache.clear()
        PinnedDataManager._pending_fetches.clear()

    @staticmethod
    def fetch_context_async(deck_id, range_type, callback, cfg=None, custom_days=7, custom_type="relative", start_date_str="", end_date_str=""):
        max_ids = _get_max_ids()
        key = (deck_id, int(range_type), int(custom_days) if custom_days is not None else 0, custom_type, start_date_str, end_date_str, max_ids)
        
        ctx = PinnedDataManager._context_cache.get(key)
        if ctx:
            callback(ctx)
            return

        from ....logic.history_cache import GlobalHistoryCache
        global_ctx = GlobalHistoryCache.get_context(
            deck_id, range_type, cfg=cfg,
            custom_days=custom_days, custom_type=custom_type,
            start_date_str=start_date_str, end_date_str=end_date_str,
            allow_sync_check=False
        )
        if global_ctx:
            if deck_id == -1:
                from ....logic.history_provider.deleted_states import enrich_deleted_context
                global_ctx = enrich_deleted_context(global_ctx)
            PinnedDataManager._context_cache[key] = global_ctx
            callback(global_ctx)
            return

        if key in PinnedDataManager._pending_fetches:
            PinnedDataManager._pending_fetches[key].append(callback)
            return
            
        log_debug(f"> [PINNED] Calling fetch_context_async: deck={deck_id}, range={range_type}", tag="PINNED")
        PinnedDataManager._pending_fetches[key] = [callback]
        
        def worker(passed_cfg=cfg):
            return fetch_pinned_context_data(
                deck_id,
                range_type,
                cfg=passed_cfg,
                custom_days=custom_days,
                custom_type=custom_type,
                start_date_str=start_date_str,
                end_date_str=end_date_str,
            )
        
        def on_done(future):
            try:
                ctx = future.result()
            except Exception:
                callbacks = PinnedDataManager._pending_fetches.pop(key, [])
                for cb in callbacks:
                    try:
                        cb({})
                    except Exception:
                        log_swallowed()
                return
            PinnedDataManager._context_cache[key] = ctx
            
            callbacks = PinnedDataManager._pending_fetches.pop(key, [])
            for cb in callbacks:
                try:
                    cb(ctx)
                except Exception as e:
                    log_error(f"Error in context callback: {e}")

        mw.taskman.run_in_background(worker, on_done=on_done)

def fetch_history_async(deck_id, range_type, callback, cache=None, history_type="reviews", custom_days=7, custom_type="relative", start_date_str="", end_date_str=""):
    """
    Fetch history in a background thread and call callback with the result.
    """
    ctx = get_pinned_context(
        deck_id,
        range_type,
        custom_days=custom_days,
        custom_type=custom_type,
        start_date_str=start_date_str,
        end_date_str=end_date_str,
    )
    if ctx:
        data = get_context_history_payload(ctx, history_type, heatmap_mode="cache_probe")
        if data:
            callback(data)
            return

    def on_context_ready(ctx):
        if history_type == "heatmap":
            # The heatmap needs both history and future data; the builder reads them from the PinnedDataManager cache, which fetch_context_async already filled in on_done.
            callback(get_context_history_payload(ctx, history_type, heatmap_mode="raw_reviews"))
            return

        data = get_context_history_payload(ctx, history_type)
        callback(data)

    PinnedDataManager.fetch_context_async(deck_id, range_type, on_context_ready, custom_days=custom_days, custom_type=custom_type, start_date_str=start_date_str, end_date_str=end_date_str)

def _history(deck_id, range_type=None, cache=None, fail_if_not_cached=False, history_type="reviews", cfg=None, custom_days=7, custom_type="relative", start_date_str="", end_date_str=""):
    if range_type is None: range_type = Period.TOTAL

    if isinstance(deck_id, list):
        ctx = get_pinned_context(
            deck_id, range_type, cfg=cfg,
            custom_days=custom_days, custom_type=custom_type,
            start_date_str=start_date_str, end_date_str=end_date_str,
            fail_if_not_cached=fail_if_not_cached,
        )
        if ctx:
            return get_context_history_payload(
                ctx,
                history_type,
                future_key="future_due",
            )
        return None if fail_if_not_cached else get_default_history_payload(history_type)

    max_ids = _get_max_ids()

    # With fail_if_not_cached, no slow O(N) slicing on the main thread
    ctx = get_pinned_context(
        deck_id, range_type, cfg=cfg, 
        custom_days=custom_days, custom_type=custom_type, 
        start_date_str=start_date_str, end_date_str=end_date_str,
        fail_if_not_cached=fail_if_not_cached,
    )
    if ctx:
        return get_context_history_payload(ctx, history_type)

    cache_key = (deck_id, int(range_type), max_ids, history_type)
    if cache is not None and cache_key in cache:
        return cache[cache_key]
    
    if fail_if_not_cached:
        return None

    # Only allow small ranges to be synchronous to avoid UI freezes on large collections
    # Period.YEAR=3, Period.TOTAL=-1, Period.CUSTOM=4
    is_large_range = False
    if range_type in [Period.YEAR, Period.LAST_YEAR, Period.TOTAL, Period.CUSTOM, Period.MONTH]:
         is_large_range = True
    elif isinstance(range_type, int) and range_type > 14: # Custom day count > 2 weeks
         is_large_range = True
         
    if is_large_range:
        return get_default_history_payload(history_type)

    cfg = _addon_config()
    if history_type == "stats":
        if is_large_range or fail_if_not_cached:
             return {}
    else:
        data = fetch_section_data(
            cfg,
            history_type,
            deck_id=deck_id,
            range_type=range_type,
        )
    if history_type == "stats":
        data = fetch_section_data(
            cfg,
            "stats",
            deck_id=deck_id,
            range_type=range_type,
        )
    
    if cache is not None:
         cache[cache_key] = data
         
    return data

