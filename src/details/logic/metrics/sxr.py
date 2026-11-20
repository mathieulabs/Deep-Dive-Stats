# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""SxR Heatmap: the review cards now by their FSRS stability and
retrievability.

sxr_points(cfg, deck, deleted): {(retrievability in 0.1 %, stability in 0.1 day): cards}, the
cards of type Review (not learning or relearning) with a memory state, their retrievability
counted as Anki counts it (fsrs_math.seconds_since_last_review). The page bins them itself
(charts/extras.js), so its bin options change nothing here. Kept until a card changes or the
day turns (context_fsrs's fingerprint), so the main screen pays it once."""

import threading
import time

from aqt import mw

from ..fsrs_math import curve_known, memory_state, retrievability, seconds_since_last_review
from ..history_provider.ops.context_fsrs import _DECAY_EXPR, _LRT_EXPR, _S_EXPR, _col_mod
from .review_buckets import did_limit as _did_limit

_CACHE = {}
_LOCK = threading.Lock()
_MAX = 16


def _read(did_limit, today):
    now = int(time.time())
    out = {}
    rows = mw.col.db.all(f"""
        SELECT {_S_EXPR}, {_DECAY_EXPR}, {_LRT_EXPR}, CASE WHEN json_valid(cards.data) THEN NULL ELSE cards.data END,
               cards.due, cards.odue, cards.odid, cards.ivl, cards.queue, cards.type
        FROM cards AS cards
        WHERE cards.type = 2 AND cards.data IS NOT NULL AND cards.data != '' {did_limit}
    """)
    for s, decay, lrt, raw, due, odue, odid, ivl, queue, ctype in rows:
        if s is None and raw is not None:
            mem = memory_state(raw)  # (binary card data: read by Anki's protobuf)
            if mem:
                s, decay, lrt = mem[0], mem[2], mem[3]
        try:
            s = float(s)
        except (TypeError, ValueError):
            continue
        if not s > 0:
            continue
        elapsed = seconds_since_last_review(lrt, due, odue, odid, ivl, queue, ctype, today, now)
        r = retrievability(elapsed / 86400.0, s, decay)
        if not 0.0 <= r <= 1.0:
            continue
        key = (int(round(r * 1000)), int(round(s * 10)))
        out[key] = out.get(key, 0) + 1
    return out


def sxr_points(addon_config, deck_id=None, is_deleted=False):
    if not curve_known():
        return {}  # another FSRS: its retrievability is not worked out here
    did_limit = _did_limit(addon_config, deck_id, is_deleted)
    today = mw.col.sched.today
    stamp = _col_mod()
    key = (did_limit, today, stamp)
    if stamp is not None:
        with _LOCK:
            hit = _CACHE.get(key)
        if hit is not None:
            return hit
    value = _read(did_limit, today)
    if stamp is not None:
        with _LOCK:
            if len(_CACHE) >= _MAX:
                _CACHE.clear()
            _CACHE[key] = value
    return value
