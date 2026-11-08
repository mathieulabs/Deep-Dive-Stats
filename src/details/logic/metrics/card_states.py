# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The state of every card on every past day (new / learning / relearning / young / mature),
rebuilt from the review history: the "time machine" charts.

A card is new from the day it was created (its id) until its first answer. After each
answer it is in learning (a learning step), relearning (a relearning step), or a review card
with the interval it was given: young below 21 days, mature from 21 days, as Anki's Card
Counts. A reset (Forget) makes it new again, a due date set (or a reschedule) makes it a
review card with that interval; filtered-deck previews change nothing. Suspended and buried
are not in the history: a card counts in its scheduling state.

The changes of state of the whole collection are read once (one pass over the review
history, in the background), then kept: after new reviews only the cards answered since are
read again. A deck is a filter on the cards (one quick query of the cards table)."""

import bisect
import threading
from datetime import date

from aqt import mw

NEW, LEARN, RELEARN, YOUNG, MATURE = range(5)
KEYS = ("new", "learn", "relearn", "young", "mature")

_LOCK = threading.Lock()
# {"col": id(col), "roll": rollover, "max_id", "count", "by_card": {cid: [(day, state), ...]}}
_STATE = {}
_AGG = {}  # aggregated timelines per deck, kept until the history or the cards change


def _day_sql(column, roll):
    """SQL of the Anki day (local date, the day starting at the rollover hour) of a ms id."""
    return f"date({column} / 1000 - {int(roll) * 3600}, 'unixepoch', 'localtime')"


_ORD = {}


def _ordinal(text):
    o = _ORD.get(text)
    if o is None:
        try:
            o = date.fromisoformat(str(text)[:10]).toordinal()
        except ValueError:
            o = 0
        if len(_ORD) > 20000:
            _ORD.clear()
        _ORD[text] = o
    return o


def _review_state(ivl):
    return MATURE if (ivl or 0) >= 21 else YOUNG


def _manual_state(rtype, ivl, factor):
    """A history entry that is not an answer: a reset (Forget), a due date set or a
    reschedule; None when it changes nothing (filtered-deck preview, unrated)."""
    if rtype == 4 and not factor and not ivl:
        return NEW
    if rtype in (4, 5) and ivl and ivl > 0:
        return _review_state(ivl)
    return None


def _events(rows, current=None):
    """[(day, state)] of one card from its history in order [(day, type, ease, ivl, factor)]:
    the state at the end of each day it changed. current: (type, ivl) of the card now.

    After an answer the card is in the state of its next answer's kind: learning before a
    learning answer, relearning before a relearning one, a review card before a review
    answer (with the interval just given). The interval alone does not tell: Anki logs a
    positive interval on an Again that sends a card to relearning (the interval it will get
    back). After the last answer, the card's state now."""
    kept = []
    for day, rtype, ease, ivl, factor in rows:
        if rtype in (0, 1, 2) and ease and ease > 0:
            kept.append((day, rtype, ivl, None))
        else:
            s = _manual_state(rtype, ivl, factor)
            if s is not None:
                kept.append((day, rtype, ivl, s))
    out = []
    for i, (day, rtype, ivl, s) in enumerate(kept):
        if s is None:
            nxt = kept[i + 1] if i + 1 < len(kept) else None
            if nxt is not None and nxt[3] is None:
                s = LEARN if nxt[1] == 0 else RELEARN if nxt[1] == 2 else _review_state(ivl)
            elif nxt is None and current is not None and current[0] in (1, 2, 3):
                ctype, civl = current
                s = LEARN if ctype == 1 else RELEARN if ctype == 3 else _review_state(civl)
            elif ivl and ivl > 0:
                s = _review_state(ivl)
            else:
                s = LEARN if rtype == 0 else RELEARN
        if out and out[-1][0] == day:
            out[-1] = (day, s)
            if len(out) > 1 and out[-2][1] == s:
                out.pop()
        elif not out or out[-1][1] != s:
            out.append((day, s))
    return out


def _read(where=""):
    from .. import rollover_hour

    roll = int(rollover_hour() or 0)
    now = {int(cid): (int(t or 0), int(ivl or 0)) for cid, t, ivl in mw.col.db.all("SELECT id, type, ivl FROM cards")}
    by_card = {}
    cur, rows = None, []
    for cid, day, rtype, ease, ivl, factor in mw.col.db.all(f"""
        SELECT cid, {_day_sql('id', roll)}, type, ease, ivl, factor
        FROM revlog {where} ORDER BY cid, id"""):
        if cid != cur:
            if rows:
                ev = _events(rows, now.get(int(cur)))
                if ev:
                    by_card[int(cur)] = ev
            cur, rows = cid, []
        rows.append((_ordinal(day), int(rtype or 0), int(ease or 0), int(ivl or 0), int(factor or 0)))
    if rows:
        ev = _events(rows, now.get(int(cur)))
        if ev:
            by_card[int(cur)] = ev
    return by_card, roll


def _all_events():
    from .. import rollover_hour

    max_id, count = mw.col.db.first("SELECT max(id), count() FROM revlog") or (None, 0)
    max_id, count = int(max_id or 0), int(count or 0)
    roll = int(rollover_hour() or 0)
    with _LOCK:
        st = dict(_STATE)
    same = st.get("col") == id(mw.col) and st.get("roll") == roll
    if same and st.get("max_id") == max_id and st.get("count") == count:
        return st["by_card"], (max_id, count)
    by_card = None
    if same and st.get("max_id") and count >= st.get("count", 0):
        new_rows = mw.col.db.scalar("SELECT count() FROM revlog WHERE id > ?", st["max_id"])
        if int(new_rows or 0) == count - st["count"]:
            # Only new reviews: the cards answered since are read again.
            from ....utils import sql_id_list

            by_card = dict(st["by_card"])
            cids = [int(c) for c in mw.col.db.list("SELECT DISTINCT cid FROM revlog WHERE id > ?", st["max_id"])]
            for i in range(0, len(cids), 500):
                chunk = cids[i:i + 500]
                fresh, _roll = _read(f"WHERE cid IN {sql_id_list(chunk)}")
                for cid in chunk:
                    if cid in fresh:
                        by_card[cid] = fresh[cid]
                    else:
                        by_card.pop(cid, None)
    if by_card is None:
        by_card, roll = _read()
    with _LOCK:
        _STATE.clear()
        _STATE.update({"col": id(mw.col), "roll": roll, "max_id": max_id, "count": count, "by_card": by_card})
        _AGG.clear()
    return by_card, (max_id, count)


class Timeline:
    """The counts of each state at the end of every day of a deck's history."""

    def __init__(self, days, counts):
        self.days = days  # sorted day ordinals where the counts change
        self.counts = counts  # counts[i]: (new, learn, relearn, young, mature) from days[i] on

    def at(self, ordinal):
        i = bisect.bisect_right(self.days, ordinal) - 1
        return self.counts[i] if i >= 0 else (0, 0, 0, 0, 0)


def timeline(addon_config, deck_id=None, is_deleted=False):
    """Timeline of the cards of the decks (the cards as they exist now)."""
    from .. import rollover_hour
    from .review_buckets import did_limit

    by_card, stamp = _all_events()
    limit = did_limit(addon_config, deck_id, is_deleted)
    roll = int(rollover_hour() or 0)
    cards_stamp = tuple(mw.col.db.first("SELECT count(), max(id), total(mod) FROM cards") or ())
    key = (limit, stamp, cards_stamp, roll)
    with _LOCK:
        hit = _AGG.get(key)
    if hit is not None:
        return hit
    delta = {}

    def move(day, state, step):
        row = delta.get(day)
        if row is None:
            row = delta[day] = [0, 0, 0, 0, 0]
        row[state] += step

    for cid, created in mw.col.db.all(
            f"SELECT cards.id, {_day_sql('cards.id', roll)} FROM cards WHERE 1 = 1 {limit}"):
        ev = by_card.get(int(cid))
        start = _ordinal(created)
        if ev and ev[0][0] <= start:
            steps = ev  # answered on (or before) the day it was made: never seen as new
        else:
            steps = [(start, NEW)] + list(ev or ())
        prev = None
        for day, state in steps:
            if prev is not None:
                move(day, prev, -1)
            move(day, state, 1)
            prev = state
    days = sorted(delta)
    counts, run = [], [0, 0, 0, 0, 0]
    for d in days:
        row = delta[d]
        run = [run[k] + row[k] for k in range(5)]
        counts.append(tuple(run))
    out = Timeline(days, counts)
    with _LOCK:
        if len(_AGG) > 12:
            _AGG.clear()
        _AGG[key] = out
    return out
