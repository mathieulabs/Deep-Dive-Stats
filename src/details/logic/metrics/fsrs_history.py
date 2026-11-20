# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The FSRS memory state (stability, difficulty) of every card after each of its reviews: the
charts of how the memory of the collection changed over time.

The states are Anki's own: the card info's history (col.card_stats_data) gives the memory state
after each entry, computed by Anki with the card's preset as it is now. Entries without one
(manual changes, reviews before FSRS could start on the card, FSRS off) are left out.

The whole collection is read once (about 1.6 s for 11,000 cards, in the background), then kept:
after new reviews only the cards answered since are read again, and so are the cards now under
another preset (their deck given another one, or the card moved to another deck); a change of
presets (new parameters, FSRS turned on or off) reads everything again. A deck is a filter on the
cards."""

import bisect
import math
import operator
import threading
import time
from array import array
from datetime import datetime, timedelta

from aqt import mw

from ..fsrs_math import DEFAULT_DECAY, _point_version, fsrs_version, preset_decay

_LOCK = threading.Lock()
# {"base": (col, rollover, presets stamp), "max_id", "count", "by_card": {cid: (days, s, d, kb, decay, secs)},
#  "confs": {cid: the preset id it was read with}, "placed": (decks sig, cards fingerprint) when last checked,
#  "rev": how many times cards were read again for a move}
_STATE = {}
_AGG = {}  # aggregated timelines per deck, kept until the history or the cards change
# the store on disk: read once per profile (path: the file read last), written in the background after a
# change; gen: bumped by clear_caches, so a save under way is dropped
_SAVE = {"path": None, "busy": False, "again": False, "gen": 0}
_DECKS = {}  # {"key": the decks table's fingerprint, "map": {deck id: preset id}, "sig"}
_DISK_VERSION = 2  # 2: each entry's time (secs)
_LEARNING = 0  # RevlogEntry.ReviewKind.LEARNING
REVIEW, BINS = 1, 20  # RevlogEntry.ReviewKind.REVIEW; Calibration's bins of predicted recall (5% each)
RATIO_STEP, RATIO_BINS = 0.1, 30  # Forgetting Curve: days since the last review / stability, by tenths, 3.0+


def _read(cids, roll):
    """{cid: (days, stabilities, difficulties, kind * 8 + button, decay, secs)} of the cards'
    entries with a memory state, oldest first (array('i'), array('f'), array('f'), array('B')),
    the decay of the card's preset (fsrs_math.preset_decay), and the time of
    each entry (array('I'), seconds: its revlog id // 1000)."""
    out = {}
    shift = timedelta(hours=roll)
    for cid in cids:
        try:
            stats = mw.col.card_stats_data(int(cid))
            entries = stats.revlog
        except Exception:
            continue  # a card deleted since its reviews
        days, ss, ds, kb, secs = array("i"), array("f"), array("f"), array("B"), array("I")
        for e in reversed(entries):  # Anki lists them newest first
            if not e.HasField("memory_state"):
                continue
            days.append((datetime.fromtimestamp(int(e.time)) - shift).date().toordinal())
            ss.append(float(e.memory_state.stability))
            ds.append(float(e.memory_state.difficulty))
            kb.append((int(e.review_kind) & 31) * 8 + (int(e.button_chosen) & 7))
            secs.append(max(0, int(e.time)))
        if days:
            params = list(getattr(stats, "fsrs_params", None) or ())
            decay = preset_decay(params) or preset_decay(()) or DEFAULT_DECAY
            out[int(cid)] = (days, ss, ds, kb, decay, secs)
    return out


def _presets_stamp():
    try:
        fsrs = bool(mw.col.get_config("fsrs", False))
    except Exception:
        fsrs = None
    # (Anki's FSRS version and Anki's own too: another one can give other memory states)
    return (fsrs, fsrs_version(), _point_version(),
            tuple(mw.col.db.first("SELECT count(), max(mtime_secs) FROM deck_config") or ()))


def _deck_presets():
    """({deck id: its preset id} of the normal decks, a signature of it), read again when a deck changes."""
    try:
        key = tuple(mw.col.db.first("SELECT count(), max(mtime_secs), total(mtime_secs) FROM decks") or ())
    except Exception:
        key = None
    key = (id(mw.col), key)
    with _LOCK:
        if _DECKS.get("key") == key:
            return _DECKS["map"], _DECKS["sig"]
    m = {}
    try:
        for d in mw.col.decks.all():
            if not d.get("dyn"):
                m[int(d["id"])] = int(d.get("conf") or 1)
    except Exception:
        from ..logger import log_swallowed

        log_swallowed()
        return m, None  # (not kept: read again next time)
    sig = hash(frozenset(m.items()))
    with _LOCK:
        _DECKS.update({"key": key, "map": m, "sig": sig})
    return m, sig


def presets_key():
    """What the cards' presets depend on: the presets themselves, and which deck uses which."""
    return _presets_stamp(), _deck_presets()[1]


def _moved(by_card, confs, placed):
    """(cards now under another preset than the one they were read with, confs, placed). Only the
    cards changed since the last check are looked at, all of them when a deck changed its preset.
    A card read with no preset known yet is taken as read with its current one."""
    dmap, sig = _deck_presets()
    if sig is None:
        return [], confs, placed  # the decks could not be read: checked next time
    fp = tuple(mw.col.db.first("SELECT count(), max(mod) FROM cards") or ())
    now = (sig, fp)
    if placed == now:
        return [], confs, placed
    if placed and placed[0] == sig and len(placed[1]) == 2 and placed[1][1] is not None:
        rows = mw.col.db.all("SELECT id, odid, did FROM cards WHERE mod >= ?", int(placed[1][1]))
    else:
        rows = mw.col.db.all("SELECT id, odid, did FROM cards")
    moved, new = [], None
    for cid, odid, did in rows:
        cid = int(cid)
        if cid not in by_card:
            continue
        p = dmap.get(int(odid or 0) or int(did))
        old = confs.get(cid)
        if old == p:
            continue
        if new is None:
            new = dict(confs)  # (the stored dict is never changed in place)
        new[cid] = p
        if old is not None:
            moved.append(cid)
    return moved, (confs if new is None else new), now


def clear_caches():
    """Empties the FSRS caches held in memory (the troubleshooting window's Clear Cache: its files go too)."""
    with _LOCK:
        _STATE.clear()
        _AGG.clear()
        _DECKS.clear()
        _SAVE["gen"] += 1
    try:
        path = _disk_path()
    except Exception:
        path = None
    with _LOCK:
        _SAVE["path"] = path  # (its file is being deleted: nothing to load)
    from ..history_provider.ops import context_fsrs
    from . import future_due, sinc, sxr

    for cache, lock in ((context_fsrs._FSRS_CACHE, context_fsrs._FSRS_CACHE_LOCK), (sinc._CACHE, sinc._LOCK),
                        (sxr._CACHE, getattr(sxr, "_LOCK", None)), (future_due._RET_CACHE, None)):
        if lock is not None:
            with lock:
                cache.clear()
        else:
            cache.clear()


def _disk_path():
    """user_files/cache/<profile>.fsrs.pkl, next to the review history cache."""
    import os

    from ..history_cache.global_cache import GlobalHistoryCache

    cache = GlobalHistoryCache()
    return os.path.join(cache.target_dir, os.path.splitext(cache.profile_cache_name)[0] + ".fsrs.pkl")


def _load_disk():
    """The store saved by an earlier session ({} if none or unreadable): only the cards answered
    since are then read again."""
    import pickle
    import zlib

    try:
        with open(_disk_path(), "rb") as f:
            raw = f.read()
        data = pickle.loads(zlib.decompress(raw))
        if isinstance(data, dict) and data.get("version") == _DISK_VERSION and isinstance(data.get("by_card"), dict):
            return {k: data[k] for k in ("base", "max_id", "count", "by_card", "confs", "placed", "rev") if k in data}
    except FileNotFoundError:
        pass
    except Exception:
        from ..logger import log_swallowed

        log_swallowed()
    return {}


def _save_disk():
    """The store written in the background (a temp file swapped in); once more if it changed meanwhile."""
    import os
    import pickle
    import zlib

    with _LOCK:
        if _SAVE["busy"]:
            _SAVE["again"] = True
            return
        _SAVE["busy"] = True

    def worker():
        try:
            while True:
                with _LOCK:
                    _SAVE["again"] = False
                    gen = _SAVE["gen"]
                    st = dict(_STATE)
                    st["by_card"] = dict(st.get("by_card") or {})  # (its entries are never changed in place)
                path = st.pop("path", None)  # the profile's file it was read for
                if not st.get("base") or not path:
                    return
                st["version"] = _DISK_VERSION
                payload = zlib.compress(pickle.dumps(st, protocol=pickle.HIGHEST_PROTOCOL), 6)
                tmp = path + ".tmp"
                with open(tmp, "wb") as f:
                    f.write(payload)
                with _LOCK:
                    dropped = gen != _SAVE["gen"]  # cleared meanwhile
                if dropped:
                    os.remove(tmp)
                    return
                os.replace(tmp, path)
                with _LOCK:
                    if not _SAVE["again"]:
                        return
        except Exception:
            from ..logger import log_swallowed

            log_swallowed()
        finally:
            with _LOCK:
                _SAVE["busy"] = False

    threading.Thread(target=worker, name="dd-fsrs-history-save", daemon=True).start()


def _all_states():
    """({cid: entries}, stamp) of the whole collection, read again only where it changed."""
    from .. import rollover_hour

    roll = int(rollover_hour() or 0)
    from .revlog_stamp import revlog_stamp
    max_id, count = revlog_stamp()  # (kept: one read of the history for all the charts)
    max_id, count = int(max_id or 0), int(count or 0)
    crt = int(mw.col.db.scalar("SELECT crt FROM col") or 0)  # the collection (kept across sessions)
    # (the time zone: the entries' days are local dates; its name, so summer time changes nothing)
    base = (crt, roll, tuple(time.tzname), _presets_stamp())
    try:
        path = _disk_path()
    except Exception:
        path = None
    with _LOCK:
        st = dict(_STATE)
        first = _SAVE["path"] != path  # this profile's file not read yet
        _SAVE["path"] = path
    if first and st.get("base") != base:
        st = _load_disk() or st
    same = st.get("base") == base
    confs = (st.get("confs") or {}) if same else {}
    placed = st.get("placed") if same else None
    rev = int(st.get("rev") or 0) if same else 0
    dirty = False
    if same and st.get("max_id") == max_id and st.get("count") == count:
        by_card = st["by_card"]  # as kept (or as saved)
    else:
        by_card = None
        if same and st.get("max_id") and count >= st.get("count", 0):
            new_rows = mw.col.db.scalar("SELECT count() FROM revlog WHERE id > ?", st["max_id"])
            if int(new_rows or 0) == count - st["count"]:
                # only new reviews: the cards answered since are read again
                cids = [int(c) for c in mw.col.db.list("SELECT DISTINCT cid FROM revlog WHERE id > ?", st["max_id"])]
                by_card = dict(st["by_card"])
                fresh = _read(cids, roll)
                if any(c in confs for c in cids):  # read again with their preset of now
                    confs = {c: p for c, p in confs.items() if c not in fresh}
                for cid in cids:
                    if cid in fresh:
                        by_card[cid] = fresh[cid]
                    else:
                        by_card.pop(cid, None)
        if by_card is None:
            by_card = _read(mw.col.db.list("SELECT DISTINCT cid FROM revlog"), roll)
            confs, placed = {}, None
        dirty = True
    moved, confs, placed = _moved(by_card, confs, placed)
    if moved:
        # under another preset now: their states were Anki's with the old one
        by_card = dict(by_card)
        fresh = _read(moved, roll)
        for cid in moved:
            if cid in fresh:
                by_card[cid] = fresh[cid]
            else:
                by_card.pop(cid, None)
        rev += 1
        dirty = True
    with _LOCK:
        _STATE.clear()
        _STATE.update({"base": base, "max_id": max_id, "count": count, "by_card": by_card,
                       "confs": confs, "placed": placed, "rev": rev, "path": path})
        if dirty:
            _AGG.clear()
    if dirty:
        _save_disk()
    return by_card, (base, max_id, count, rev)


class DeckCards:
    """The entries of a deck's cards (a list of (days, s, d, kb, decay, secs)), with the key the
    aggregations over them are kept under, and the card ids (cids[i]: the card of cards[i])."""

    def __init__(self, key, cards, cids=()):
        self.key = key
        self.cards = cards
        self.cids = cids


def _kept(key, make):
    with _LOCK:
        hit = _AGG.get(key)
    if hit is not None:
        return hit
    out = make()
    with _LOCK:
        if len(_AGG) > 24:
            _AGG.clear()
        _AGG[key] = out
    return out


def deck_cards(addon_config, deck_id=None, is_deleted=False):
    """DeckCards of the cards of the decks (the cards as they exist now)."""
    from .review_buckets import did_limit

    by_card, stamp = _all_states()
    limit = did_limit(addon_config, deck_id, is_deleted)
    cards_stamp = tuple(mw.col.db.first("SELECT count(), max(id), total(mod) FROM cards") or ())
    key = ("cards", limit, stamp, cards_stamp)
    def make():
        cids = [int(cid) for (cid,) in mw.col.db.all(f"SELECT cards.id FROM cards WHERE 1 = 1 {limit}")
                if int(cid) in by_card]
        return DeckCards(key, [by_card[c] for c in cids], cids)
    return _kept(key, make)


def states_at(src, ordinal):
    """{"stability": {days: cards}, "difficulty": {percent: cards}} of the cards' memory states at
    the end of a day, binned as Card Stability / Card Difficulty do today (fsrs_math): stability
    rounded to days (100 for 100 or more), difficulty in 1% bins. A card with no memory state yet
    that day is left out."""
    def make():
        stab, diff = {}, {}
        for days, ss, ds, *_rest in src.cards:
            i = bisect.bisect_right(days, ordinal) - 1
            if i < 0:
                continue
            s = ss[i]
            sb = min(int(s + 0.5), 100) if s > 0 else 0
            stab[sb] = stab.get(sb, 0) + 1
            db = max(0, min(99, int(((ds[i] - 1.0) / 9.0 * 100.0) // 1)))
            diff[db] = diff.get(db, 0) + 1
        return {"stability": stab, "difficulty": diff}
    return _kept(("at", int(ordinal)) + src.key[1:], make)


class LevelTimeline:
    """A value at the end of every day from day `first` to today (0 before)."""

    def __init__(self, first, values):
        self.first = first
        self.values = values

    def at(self, ordinal):
        i = ordinal - self.first
        if i < 0 or not self.values:
            return 0.0
        return self.values[min(i, len(self.values) - 1)]


_S_STEP = math.log(1.01)  # Memorised: the stabilities by 1% steps, one recall curve each


def _today():
    from .. import rollover_hour

    return (datetime.now() - timedelta(hours=int(rollover_hour() or 0))).date().toordinal()


MEMORISED_MEASURES = ("cards", "notes", "average", "load", "stable")
_STABLE_K = 8.0 / 365.0  # Retrievability & Stability: a card counts by 1 - e^(-k S), well kept ones about 1


def memorised(src, measure="cards"):
    """LevelTimeline of how many cards were known at the end of each day: the sum over the cards
    of their probability of recall (FSRS, from their memory state after their last review before;
    1 on the day of a review). A card counts from its first memory state on.

    measure: "cards" that sum; "notes": each card's
    recall over the cards of its note (a note known when all its cards are); "average": the sum
    over the cards with a memory state that day, in percent; "stable": each recall weighted by
    1 - e^(-8/365 S), the cards both recalled and lasting. ("load": memorised_per_load.)"""
    if measure not in ("cards", "notes", "average", "stable"):
        measure = "cards"

    def make():
        today = _today()
        firsts = [c[0][0] for c in src.cards if c[0]]
        if not firsts:
            return LevelTimeline(today, [])
        first = min(min(firsts), today)
        tot = [0.0] * (today - first + 1)
        weights = None
        if measure == "notes":
            nid_of = dict(mw.col.db.all("SELECT id, nid FROM cards"))
            size = {}
            for cid in src.cids:
                n = nid_of.get(cid)
                size[n] = size.get(n, 0) + 1
            weights = [1.0 / size.get(nid_of.get(cid), 1) for cid in src.cids]
        curves = {}
        add = operator.add
        for ci, (days, ss, _ds, _kb, decay, *_r) in enumerate(src.cards):
            last = len(days) - 1
            dk = round(decay, 4)
            wc = weights[ci] if weights is not None else 1.0
            for i in range(last + 1):
                if i < last and days[i + 1] == days[i]:
                    continue  # a later state the same day
                a = days[i]
                e = days[i + 1] if i < last else today + 1
                e = min(e, today + 1)
                if e <= a or a > today:
                    continue
                s = ss[i]
                if s <= 0:
                    continue
                n = e - a
                b = round(math.log(s) / _S_STEP)
                c = curves.get((dk, b))
                if c is None or len(c) < n:
                    sb = math.exp(b * _S_STEP)
                    factor = 0.9 ** (-1.0 / dk) - 1.0
                    size_ = max(n, 2 * len(c) if c else 64)
                    c = curves[(dk, b)] = [(1.0 + factor * t / sb) ** (-dk) for t in range(size_)]
                lo = a - first
                k = wc * (1.0 - math.exp(-_STABLE_K * s)) if measure == "stable" else wc
                if k == 1.0:
                    tot[lo:lo + n] = map(add, tot[lo:lo + n], c[:n])
                else:
                    tot[lo:lo + n] = [x + k * y for x, y in zip(tot[lo:lo + n], c[:n])]
        if measure == "average":
            # over the cards with a memory state by then
            count = [0] * (today - first + 2)
            for f in firsts:
                if f <= today:
                    count[f - first] += 1
            n = 0
            for i in range(len(tot)):
                n += count[i]
                tot[i] = tot[i] * 100.0 / n if n else 0.0
        return LevelTimeline(first, tot)
    return _kept(("memorised", measure, _today()) + src.key[1:], make)


class StabilityTimeline:
    """The stability of a deck's cards with a memory state at the end of every day of its
    history: mean, median, the share of young cards (stability under 21 days), the mean
    difficulty and how many cards."""

    def __init__(self, days, values):
        self.days = days  # sorted day ordinals where the values change
        self.values = values  # values[i]: (mean S, median S, young share, mean D, cards) from days[i] on

    def at(self, ordinal):
        i = bisect.bisect_right(self.days, ordinal) - 1
        return self.values[i] if i >= 0 else (0.0, 0.0, 0.0, 0.0, 0)


_YOUNG_S = 21.0  # a stability under 21 days: a young card
_FEN_LO, _FEN_HI = -800, 1500  # the stabilities by 1% steps (log), from 0.0003 to about 3 million days


def stability_levels(src):
    """StabilityTimeline of the cards (a card counts from its first memory state on, with its last
    state of each day). The median is read from a count of the cards by 1% steps of stability."""
    def make():
        delta = {}  # day -> [(old S or None, new S, old D, new D)]
        for days, ss, ds, *_rest in src.cards:
            prev = None
            last = len(days) - 1
            for i in range(last + 1):
                if i < last and days[i + 1] == days[i]:
                    continue
                delta.setdefault(days[i], []).append((prev, ss[i], ds[i]))
                prev = (ss[i], ds[i])
        size = _FEN_HI - _FEN_LO + 1
        tree = [0] * (size + 1)

        def bin_of(s):
            b = round(math.log(s) / _S_STEP) if s > 0 else _FEN_LO
            return min(max(b, _FEN_LO), _FEN_HI) - _FEN_LO + 1  # 1-based

        def bump(i, v):
            while i <= size:
                tree[i] += v
                i += i & -i

        top = 1 << (size.bit_length() - 1)

        def kth(k):  # the bin of the k-th smallest stability (1-based)
            pos, step = 0, top
            while step:
                nxt = pos + step
                if nxt <= size and tree[nxt] < k:
                    pos = nxt
                    k -= tree[nxt]
                step >>= 1
            return pos + 1

        out_days, values = [], []
        s_sum = d_sum = 0.0
        n = young = 0
        for day in sorted(delta):
            for prev, s, d in delta[day]:
                if prev is None:
                    n += 1
                else:
                    bump(bin_of(prev[0]), -1)
                    s_sum -= prev[0]
                    d_sum -= prev[1]
                    young -= prev[0] < _YOUNG_S
                bump(bin_of(s), 1)
                s_sum += s
                d_sum += d
                young += s < _YOUNG_S
            if n:
                at = lambda k: math.exp((kth(k) - 1 + _FEN_LO) * _S_STEP)
                med = at((n + 1) // 2) if n % 2 else (at(n // 2) + at(n // 2 + 1)) / 2.0
                values.append((s_sum / n, med, young / n, d_sum / n, n))
            else:
                values.append((0.0, 0.0, 0.0, 0.0, 0))
            out_days.append(day)
        return StabilityTimeline(out_days, values)
    return _kept(("stab_levels",) + src.key[1:], make)


def recall(t, s, decay):
    """FSRS's probability of recall t days after a review, for a stability s (days)."""
    factor = 0.9 ** (-1.0 / decay) - 1.0
    return (1.0 + factor * t / s) ** (-decay)


def review_points(cards, lo, hi):
    """Each review answer (kind Review, a day or more after the card's previous entry) from day
    lo to day hi: (days since the previous entry, the stability then, the recall FSRS predicted,
    passed). The stability before an answer is the memory state after the previous entry."""
    for days, ss, _ds, kb, decay, *_r in cards:
        for i in range(1, len(days)):
            day = days[i]
            if day < lo or day > hi:
                continue
            k = kb[i]
            if (k >> 3) != REVIEW or not (k & 7):
                continue
            t = day - days[i - 1]
            s = ss[i - 1]
            if t < 1 or s <= 0:
                continue
            yield t, s, recall(t, s, decay), (k & 7) > 1


def _binned(src, lo, hi, kind):
    """{bin: [failed, passed, sum of predicted recall]} of the reviews from day lo to day hi:
    by predicted recall (Calibration) or by days since the last review / stability (Forgetting
    Curve)."""
    def make():
        out = {}
        for t, s, r, ok in review_points(src.cards, lo, hi):
            b = min(BINS - 1, int(r * BINS)) if kind == "calibration" else min(RATIO_BINS, int(t / s / RATIO_STEP))
            row = out.get(b)
            if row is None:
                row = out[b] = [0, 0, 0.0]
            row[1 if ok else 0] += 1
            row[2] += r
        return out
    return _kept((kind, int(lo), int(hi)) + src.key[1:], make)


def calibration(src, lo, hi):
    return _binned(src, lo, hi, "calibration")


def forgetting(src, lo, hi):
    return _binned(src, lo, hi, "forgetting")


BW_POWER = 1.4  # B-W Matrix: its rows of stability, 1.4 times the one below


def bw_matrix(src):
    """B-W Matrix: {(row, difficulty): [answers, passed, sum of predicted
    recall]} of the answers a day or more after the card's previous entry whose stability then was
    over a day, over the whole history: row k holds the stabilities from 1.4^k to 1.4^(k+1) days,
    the difficulty then rounded (1 to 10). A card learnt again from the start (Forget) is not
    counted on its first step (its state then was the old one); manual entries are left out."""
    def make():
        out = {}
        lg = math.log(BW_POWER)
        for days, ss, ds, kb, decay, *_r in src.cards:
            for i in range(1, len(days)):
                k = kb[i]
                kind = k >> 3
                if not (k & 7) or kind > 3:
                    continue
                if kind == _LEARNING and (kb[i - 1] >> 3) != _LEARNING:
                    continue
                t = days[i] - days[i - 1]
                s = ss[i - 1]
                if t < 1 or s <= 1.0:
                    continue
                key = (int(math.floor(math.log(s) / lg + 1e-9)), min(10, max(1, int(ds[i - 1] + 0.5))))
                cell = out.get(key)
                if cell is None:
                    cell = out[key] = [0, 0, 0.0]
                cell[0] += 1
                if (k & 7) > 1:
                    cell[1] += 1
                cell[2] += recall(t, s, decay)
        return out
    return _kept(("bw",) + src.key[1:], make)


def _day_ranks(lo, hi):
    """(secs, ranks): the time of each review answer from day lo to day hi (array('q'), sorted)
    and its place in its day (array('i')), as Rating Fatigue counts it (review_buckets.fatigue_counts):
    every answer of the day, whatever its deck."""
    from .review_buckets import MAX_POSITION

    today = _today()
    cutoff = int(mw.col.sched.day_cutoff)
    base = cutoff - 86400 * 40000  # days counted from far back: the division stays on positive numbers
    start = (cutoff - 86400 * (today - int(lo) + 1)) * 1000
    end = (cutoff - 86400 * (today - int(hi))) * 1000
    secs, ranks = array("q"), array("i")
    for sec, n in mw.col.db.all(f"""
            SELECT id / 1000, ROW_NUMBER() OVER (PARTITION BY (id / 1000 - {base}) / 86400 ORDER BY id)
            FROM revlog
            WHERE id >= {int(start)} AND id < {int(end)} AND type < 4 AND ease BETWEEN 1 AND 4
            ORDER BY id"""):
        secs.append(int(sec))
        ranks.append(min(int(n), MAX_POSITION))
    return secs, ranks


def fatigue_loss(src, lo, hi, kinds=None):
    """FSRS Loss by Fatigue: {place of the answer in its day: [answers,
    passed, sum of predicted recall]} of the review answers (kind Review, a day or more after
    the card's previous entry) from day lo to day hi. The place counts every answer of the day
    (as Rating Fatigue); the deck only picks which answers are counted. kinds: only those card kinds
    (review_buckets.kinds_of: 1 young, 2 mature, by the days since the previous entry, mature from 21)."""
    def make():
        secs, ranks = _day_ranks(lo, hi)
        out = {}
        if not secs:
            return out
        find = bisect.bisect_left
        top = len(secs)
        for days, ss, _ds, kb, decay, tsec in src.cards:
            for i in range(1, len(days)):
                day = days[i]
                if day < lo or day > hi:
                    continue
                k = kb[i]
                if (k >> 3) != REVIEW or not (k & 7):
                    continue
                t = day - days[i - 1]
                s = ss[i - 1]
                if t < 1 or s <= 0:
                    continue
                if kinds and (2 if t >= 21 else 1) not in kinds:
                    continue
                j = find(secs, tsec[i])
                if j >= top or secs[j] != tsec[i]:
                    continue  # (not in the revlog any more)
                row = out.get(ranks[j])
                if row is None:
                    row = out[ranks[j]] = [0, 0, 0.0]
                row[0] += 1
                if (k & 7) > 1:
                    row[1] += 1
                row[2] += recall(t, s, decay)
        return out
    return _kept(("fatigue", int(lo), int(hi), _today(), tuple(kinds or ())) + src.key[1:], make)


LEECH_BINS = 19  # Leech Detector: 5% bins from 5% to 100%


def _leech_odds(days, ss, kb, decay):
    """How unlikely a card's lapses are: 1 - the chance,
    from the recall FSRS predicted before each answer (a review two days or more after the
    previous entry), of passing no more often than it did (a Poisson binomial, its passes kept up
    to those seen). 0 below two passes. A card learnt again from the start (Forget) starts over."""
    p_ = [1.0]
    for i in range(1, len(days)):
        k = kb[i]
        kind = k >> 3
        if kind == _LEARNING and (kb[i - 1] >> 3) != _LEARNING:
            p_ = [1.0]  # forgotten, learnt again
            continue
        if not (k & 7) or kind > 3:
            continue
        t = days[i] - days[i - 1]
        s = ss[i - 1]
        if t < 2 or s <= 0:
            continue
        p = recall(t, s, decay)
        q = 1.0 - p
        if (k & 7) > 1:
            p_.append(0.0)
        p_ = [a * q + b * p for a, b in zip(p_, [0.0] + p_[:-1])]
    if len(p_) <= 2:
        return 0.0
    return max(0.0, 1.0 - sum(p_))


def leech_odds(src):
    """Leech Detector: ([cards in each 5% bin of the odds, from 5% to 100%], [(bin, cid)] of the
    cards in a bin), over the whole history of the deck's cards."""
    def make():
        counts = [0] * LEECH_BINS
        where = []
        cids = src.cids or ()
        for n, (days, ss, _ds, kb, decay, *_r) in enumerate(src.cards):
            x = _leech_odds(days, ss, kb, decay)
            if x < 0.05:
                continue
            b = min(LEECH_BINS - 1, int(x * 20 + 1e-9) - 1)
            counts[b] += 1
            if n < len(cids):
                where.append((b, cids[n]))
        return counts, where
    return _kept(("leech",) + src.key[1:], make)
