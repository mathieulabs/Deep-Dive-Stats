# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""First Long-term / Short-term Forgetting Curve: how the cards were
recalled after their first rating, by that first rating, with a FSRS forgetting curve fitted to
each.

One sample per card: the first answer on a later day than its first rating (long-term, delta in
days), or its first answer within 24 hours of it (short-term, delta in minutes; cards first rated
Easy left out). The first rating is the card's first answer in learning; a card reset (Forget)
starts over; cramming answers (filtered deck, no rescheduling) are skipped. The whole history of
the deck's cards."""

import math

from aqt import mw

from .review_buckets import _join, _memo

FSRS5_DEFAULT_DECAY = 0.5  # a card without a decay in its data
DEFAULT_S = {1: 0.212, 2: 1.2931, 3: 2.3065, 4: 8.2956}  # FSRS-6's first stabilities: the fit's start
_EPS = 1e-6
_DAY_MS = 86400000


def _recall(t, s, decay):
    factor = 0.9 ** (-1.0 / decay) - 1.0
    return (1.0 + factor * t / s) ** (-decay)


def _short_delta(minutes):
    """Minutes kept to a tenth below 10, to the minute above (fewer points to send, the same fit)."""
    return round(minutes, 1) if minutes < 10 else float(round(minutes))


def _samples(limit, short):
    """({rating: {delta: [passed, count]}}, cids of the samples)."""
    cutoff = int(mw.col.sched.day_cutoff)
    base = cutoff - 86400 * 40000
    rows = mw.col.db.all(f"""
        SELECT revlog.cid, revlog.id, revlog.ease, revlog.type, revlog.factor
        FROM revlog {_join(limit)}
        WHERE 1 = 1 {limit}
        ORDER BY revlog.cid, revlog.id""")
    out = {1: {}, 2: {}, 3: {}, 4: {}}
    cids = []
    cur = None
    first = first_day = first_ms = None
    sample = None
    done = False

    def flush():
        if sample is not None:
            rating, delta, ok = sample
            cell = out[rating].setdefault(delta, [0, 0])
            cell[0] += ok
            cell[1] += 1
            cids.append(cur)

    for cid, rid, ease, rtype, factor in rows:
        if cid != cur:
            flush()
            cur, first, first_day, first_ms, sample, done = cid, None, None, None, None, False
        has = ease > 0
        if not has and factor == 0:  # reset (Forget): the card starts over
            first = first_day = first_ms = sample = None
            done = False
            continue
        if not has or (rtype == 3 and factor == 0):  # (cramming)
            continue
        if first is None and rtype == 0:
            first, first_ms, first_day = int(ease), rid, (rid // 1000 - base) // 86400
            continue
        if first is None or done:
            continue
        ok = 1 if ease > 1 else 0
        if short:
            if first == 4:
                continue
            dms = rid - first_ms
            if 0 < dms < _DAY_MS:
                sample = (first, _short_delta(dms / 60000.0), ok)
                done = True
        else:
            dt = (rid // 1000 - base) // 86400 - first_day
            if dt > 0:
                sample = (first, int(dt), ok)
                done = True
    flush()
    return out, cids


def _decay(cids):
    """The average decay of the cards (their FSRS data; 0.5 when they have none)."""
    if not cids:
        return FSRS5_DEFAULT_DECAY
    found = {}
    for i in range(0, len(cids), 900):
        part = cids[i:i + 900]
        for cid, d in mw.col.db.all(
                f"SELECT id, json_extract(data, '$.decay') FROM cards WHERE id IN ({','.join('?' * len(part))}) "
                f"AND json_valid(data)", *part):
            if d is not None:
                found[int(cid)] = float(d)
    vals = [found.get(int(c), FSRS5_DEFAULT_DECAY) for c in cids]
    return sum(vals) / len(vals)


def fit_stability(cells, initial, decay, lo, hi):
    """The stability whose curve fits the samples best: log loss with a small pull towards the start
    value, a ternary search, then a few candidates around it."""
    if not cells:
        return None
    items = list(cells.items())

    def loss(s):
        total = abs(s - initial) / 16.0
        for delta, (ok, n) in items:
            p = min(1 - _EPS, max(_EPS, _recall(delta, s, decay)))
            total -= ok * math.log(p) + (n - ok) * math.log(1 - p)
        return total

    left, right = lo, hi
    for _ in range(60):
        m1 = left + (right - left) / 3
        m2 = right - (right - left) / 3
        if loss(m1) > loss(m2):
            left = m1
        else:
            right = m2
    best, best_loss = initial, float("inf")
    for c in (left, right, (left + right) / 2, initial, initial * 0.5, initial * 1.5):
        c = max(lo, min(hi, c))
        v = loss(c)
        if v < best_loss:
            best, best_loss = c, v
    return best


def first_curve(limit, short=False):
    """{"series": [{"rating", "stability" (days, or minutes when short; None without samples),
    "n", "points": [[delta, passed, count], ...] by delta}], "decay", "short"}."""
    def compute():
        cells, cids = _samples(limit, short)
        decay = _decay(cids)
        lo, hi = (0.01, 1440.0) if short else (1e-3, 100.0)
        series = []
        for r in (1, 2, 3, 4):
            c = cells[r]
            n = sum(v[1] for v in c.values())
            s = fit_stability(c, DEFAULT_S[r], decay, lo, hi) if n else None
            series.append({"rating": r, "stability": s, "n": n,
                           "points": [[d, v[0], v[1]] for d, v in sorted(c.items())]})
        return {"series": series, "decay": decay, "short": bool(short)}
    return _memo(("first_curve", limit, bool(short), int(mw.col.sched.day_cutoff)), compute)
