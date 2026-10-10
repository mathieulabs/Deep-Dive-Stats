# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Compute the per-deck data pinned widgets need in a worker thread.

Widgets are built on the main thread, but their data (history contexts, FSRS
stats) can be prepared elsewhere. The worker fills the same memos first, and
if it is not done in time the main thread computes the value itself.
"""

from ..imports import Period, mw
from .....logic.logger import log_swallowed

_WARMED = set()
_WARMED_MAX = 64


def _spans_for(manager, defs):
    spans = {(int(Period.TOTAL), 7, "relative", "", "")}
    for wdef in defs:
        wtype = wdef.get("type", "")
        try:
            span = manager._normalize_time_span(wdef.get("time_span"), wtype)
            spans.add(
                (
                    int(span),
                    int(wdef.get("custom_days", 7) or 7),
                    (wdef.get("custom_type") or "relative"),
                    (wdef.get("start_date_str") or ""),
                    (wdef.get("end_date_str") or ""),
                )
            )
        except Exception:
            continue
    if any(d.get("type") == "heatmap" for d in defs):
        # Pinned heatmaps ask for the context of the displayed year.
        try:
            from datetime import datetime

            year = manager._normalize_time_span(datetime.now().year, "heatmap")
            spans.add((int(year), 7, "relative", "", ""))
        except Exception:
            log_swallowed()
    return spans


def prewarm_deck_data(manager, deck_id, defs):
    if not isinstance(deck_id, int) or deck_id in (-1, 0):
        return
    if not mw.col:
        return
    from ...widget_factory.utils import PinnedDataManager, cache_data_version

    try:
        today = mw.col.sched.today
    except Exception:
        today = None
    token = (deck_id, cache_data_version(), today, id(mw.col))
    if token in _WARMED:
        return
    if len(_WARMED) >= _WARMED_MAX:
        _WARMED.clear()
    _WARMED.add(token)

    cm = manager._config_manager
    spans = _spans_for(manager, defs)
    types = {d.get("type", "") for d in defs}
    want_fsrs = bool(types & {"difficulty", "stability", "retrievability"})

    def _work():
        for span, days, ctype, start, end in spans:
            try:
                PinnedDataManager.get_context(
                    deck_id,
                    span,
                    cfg=cm,
                    custom_days=days,
                    custom_type=ctype,
                    start_date_str=start,
                    end_date_str=end,
                    allow_slow_ops=True,
                )
            except Exception:
                log_swallowed()
        for wdef in defs:
            if wdef.get("type") != "stat_card":
                continue
            span = wdef.get("time_span", Period.TOTAL)
            if int(span) not in (int(Period.TODAY), int(Period.YESTERDAY)):
                continue
            try:
                from ...widget_factory.builders.stat_card import _build_stat_values_map

                _build_stat_values_map(
                    deck_id, span, wdef.get("custom_days", 7), fail_if_not_cached=False, cfg=cm
                )
            except Exception:
                log_swallowed()
        if want_fsrs:
            try:
                from ...widget_factory.builders.fsrs_common import fetch_fsrs_data

                fetch_fsrs_data(deck_id, cm)
            except Exception:
                log_swallowed()
        return True

    mw.taskman.run_in_background(_work)
