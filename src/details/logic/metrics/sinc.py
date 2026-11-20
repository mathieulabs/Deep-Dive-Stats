# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Stability Increase Factor: for each card, how much its FSRS
stability would grow on a Good answered on its due day.

factors(cfg, deck, deleted): [(card id, factor)], the cards with a memory state (not new): the
interval its preset's FSRS gives for the card's desired retention (rounded, 1 day to the preset's
maximum interval, no fuzz), the recall then, and FSRS's stability after a successful review with
its preset's parameters (the defaults when it has none); the factor is the new stability over the
old. Kept until a card or a preset changes, or the day turns.

binned(pairs): the bars (BINS of them, from 1x to about the 99th percentile, the last one holding
the cards above) and where each card goes, shared by the chart and its click (the browser)."""

import json
import math
import threading

from aqt import mw

from ..fsrs_math import KNOWN_VERSIONS, fsrs_version
from ..history_provider.ops.context_fsrs import _col_mod
from .review_buckets import did_limit as _did_limit

BINS = 30
# The default parameters of each FSRS version (a preset never optimized), as in fsrs-rs.
DEFAULT_W = {
    6: (0.212, 1.2931, 2.3065, 8.2956, 6.4133, 0.8334, 3.0194, 0.001, 1.8722, 0.1666, 0.796, 1.4835, 0.0614,
        0.2629, 1.6483, 0.6014, 1.8729, 0.5425, 0.0912, 0.0658, 0.1542),
    5: (0.40255, 1.18385, 3.173, 15.69105, 7.1949, 0.5345, 1.4604, 0.0046, 1.54575, 0.1192, 1.01925, 1.9395, 0.11,
        0.29605, 2.2698, 0.2315, 2.9898, 0.51655, 0.6621),
    4: (0.4872, 1.4003, 3.7145, 13.8206, 5.1618, 1.2298, 0.8975, 0.031, 1.6474, 0.1367, 1.0461, 2.1072, 0.0793,
        0.3246, 1.587, 0.2272, 2.8755),
}
# The preset fields, newest first, with the first FSRS version that reads each.
_FIELDS = (("fsrsParams6", 6), ("fsrsParams5", 5), ("fsrsWeights", 4))

_CACHE = {}
_LOCK = threading.Lock()
_MAX = 16


def _params(conf, version):
    """The parameters Anki runs for a preset: the first non-empty field its FSRS version reads
    (17, 19 or 21 of them, told apart by their number), else that version's defaults; None when
    they are not known here."""
    if version not in KNOWN_VERSIONS:
        return None
    for key, since in _FIELDS:
        w = conf.get(key) or []
        if since <= version and w:
            if len(w) not in (17, 19, 21) or (len(w) == 21 and version < 6):
                return None
            try:
                return [float(x) for x in w]
            except (TypeError, ValueError):
                return None
    return list(DEFAULT_W[version])


def factor(s, d, dr, w, max_ivl=36500):
    """The stability after a Good on the day the desired retention dr is reached, over s."""
    decay = -w[20] if len(w) >= 21 else -0.5
    f = math.pow(0.9, 1.0 / decay) - 1.0
    t = s / f * (math.pow(dr, 1.0 / decay) - 1.0)
    t = min(max(round(t), 1), max(1, int(max_ivl)))
    r = math.pow(1.0 + f * t / s, decay)
    return 1.0 + math.exp(w[8]) * (11.0 - d) * math.pow(s, -w[9]) * (math.exp(w[10] * (1.0 - r)) - 1.0)


def _read(did_limit):
    rows = mw.col.db.all(f"""
        SELECT cards.id, CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END, cards.data
        FROM cards AS cards
        WHERE cards.type != 0 AND cards.data IS NOT NULL AND cards.data != '' {did_limit}
    """)
    version = fsrs_version()
    if version not in KNOWN_VERSIONS:
        return []  # another FSRS: its stability formula is not known here
    presets = {}

    def preset(did):
        if did not in presets:
            try:
                conf = mw.col.decks.config_dict_for_deck_id(did) or {}
            except Exception:
                conf = {}
            dr = conf.get("desiredRetention") or 0.9
            presets[did] = (_params(conf, version), float(dr), int((conf.get("rev") or {}).get("maxIvl") or 36500))
        return presets[did]

    out = []
    for cid, did, raw in rows:
        try:
            jd = json.loads(raw) if isinstance(raw, str) else None
        except ValueError:
            jd = None
        if not isinstance(jd, dict):
            continue  # (binary card data: no desired retention in it)
        try:
            s, d = float(jd["s"]), float(jd["d"])
        except (KeyError, TypeError, ValueError):
            continue
        if not s > 0:
            continue
        w, dr0, max_ivl = preset(did)
        if w is None:
            continue
        try:
            dr = float(jd.get("dr") or dr0)
            if 0.0 < dr < 1.0:
                out.append((int(cid), factor(s, d, dr, w, max_ivl)))
        except (OverflowError, ValueError, ZeroDivisionError, IndexError):
            continue
    return out


def factors(addon_config, deck_id=None, is_deleted=False):
    from .fsrs_history import presets_key

    did_limit = _did_limit(addon_config, deck_id, is_deleted)
    stamp = _col_mod()
    key = (did_limit, stamp, presets_key())
    if stamp is not None:
        with _LOCK:
            hit = _CACHE.get(key)
        if hit is not None:
            return hit
    value = _read(did_limit)
    if stamp is not None:
        with _LOCK:
            if len(_CACHE) >= _MAX:
                _CACHE.clear()
            _CACHE[key] = value
    return value


def binned(pairs):
    """(width of a bar, [cards per bar], {card id: its bar}), or None (no card). The bars start at
    1x; their width is round (hundredths) and BINS of them reach about the 99th percentile."""
    if not pairs:
        return None
    fs = sorted(f for _cid, f in pairs)
    top = fs[min(len(fs) - 1, int(len(fs) * 0.99))]
    width = max(1, math.ceil((top - 1.0) * 100.0 / BINS)) / 100.0
    counts = [0] * BINS
    where = {}
    for cid, f in pairs:
        b = min(BINS - 1, max(0, int((f - 1.0) / width + 1e-9)))
        counts[b] += 1
        where[cid] = b
    return width, counts, where
