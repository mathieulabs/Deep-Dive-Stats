# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Introduced cards: the first time each card was answered (its first rated review), and the
first answer after each reset ("Forget": a manual entry without ease factor), as Search Stats
Extended counts them.

introduction_events(cfg, deck, deleted): [(review id in ms, rating 1-4, re-introduced)].

The events of the whole collection are read once (two grouped queries, about a quarter of a
second for a million reviews), then kept: after new reviews only the cards answered since are
read again (a few milliseconds), so a review session never pays the full read again. A deck
is a filter on the cards (one quick query of the cards table)."""

import threading

from aqt import mw

from ..history_provider import HistoryProvider

_LOCK = threading.Lock()
# {"col": id(col), "max_id", "count", "by_card": {cid: [(id, ease, reintro), ...]}}
_STATE = {}


def _full_read():
    """{cid: [(id, ease, reintro)]} of the whole collection (two grouped queries)."""
    by_card = {}
    for rid, ease, cid in mw.col.db.all("""
        SELECT r.id, r.ease, r.cid
        FROM revlog AS r
        JOIN (SELECT cid, MIN(id) AS mid FROM revlog WHERE type < 4 AND ease > 0 GROUP BY cid) AS m
          ON r.id = m.mid
    """):
        by_card.setdefault(int(cid), []).append((int(rid), int(ease), False))
    first_ids = {e[0] for evs in by_card.values() for e in evs}
    # The first rated review after each reset (several resets in a row: one re-introduction).
    for rid, ease, cid in mw.col.db.all("""
        SELECT DISTINCT n.id, n.ease, n.cid
        FROM (SELECT (SELECT MIN(r.id) FROM revlog AS r
                      WHERE r.cid = f.cid AND r.id > f.id AND r.type < 4 AND r.ease > 0) AS nid
              FROM revlog AS f
              WHERE f.type = 4 AND f.factor = 0) AS x
        JOIN revlog AS n ON n.id = x.nid
    """):
        if rid not in first_ids:
            by_card.setdefault(int(cid), []).append((int(rid), int(ease), True))
    for evs in by_card.values():
        evs.sort()
    return by_card


def _card_events(rows):
    """The events of one card from its reviews in order (id, ease, type, factor): the same
    rules as _full_read."""
    out = []
    introduced = False
    seen = False
    for rid, ease, rtype, factor in rows:
        if rtype == 4 and not factor:
            introduced = False
        elif rtype < 4 and ease and ease > 0 and not introduced:
            out.append((int(rid), int(ease), seen))
            introduced = seen = True
    return out


def _refresh_cards(by_card, cids):
    """Read again the events of these cards (after new reviews)."""
    from ....utils import sql_id_list

    cids = [int(c) for c in cids]
    for i in range(0, len(cids), 500):
        chunk = cids[i:i + 500]
        rows = {}
        for rid, cid, ease, rtype, factor in mw.col.db.all(
                f"SELECT id, cid, ease, type, factor FROM revlog WHERE cid IN {sql_id_list(chunk)} ORDER BY id"):
            rows.setdefault(int(cid), []).append((rid, ease, rtype, factor))
        for cid in chunk:
            evs = _card_events(rows.get(cid, []))
            if evs:
                by_card[cid] = evs
            else:
                by_card.pop(cid, None)


def _all_events():
    max_id, count = mw.col.db.first("SELECT max(id), count() FROM revlog") or (None, 0)
    max_id, count = int(max_id or 0), int(count or 0)
    with _LOCK:
        st = dict(_STATE)
    same_col = st.get("col") == id(mw.col)
    if same_col and st.get("max_id") == max_id and st.get("count") == count:
        return st["by_card"]
    by_card = None
    if same_col and st.get("max_id") and count >= st.get("count", 0):
        new_rows = mw.col.db.scalar("SELECT count() FROM revlog WHERE id > ?", st["max_id"])
        if int(new_rows or 0) == count - st["count"]:
            # Only new reviews (no undo, no deletion): read again the cards answered since.
            by_card = dict(st["by_card"])
            _refresh_cards(by_card, mw.col.db.list("SELECT DISTINCT cid FROM revlog WHERE id > ?", st["max_id"]))
    if by_card is None:
        by_card = _full_read()
    with _LOCK:
        _STATE.clear()
        _STATE.update({"col": id(mw.col), "max_id": max_id, "count": count, "by_card": by_card})
    return by_card


def introduction_events(addon_config, deck_id=None, is_deleted=False):
    by_card = _all_events()
    if is_deleted:
        alive = set(mw.col.db.list("SELECT id FROM cards"))
        keep = [c for c in by_card if c not in alive]
    else:
        did_limit = HistoryProvider._get_did_limit(addon_config, deck_id)
        if did_limit.strip():
            keep = mw.col.db.list(f"SELECT cards.id FROM cards WHERE 1 = 1 {did_limit}")
        else:
            keep = list(by_card)  # the whole collection, deleted cards' history included
    events = []
    for cid in keep:
        events.extend(by_card.get(cid, ()))
    events.sort()
    return events
