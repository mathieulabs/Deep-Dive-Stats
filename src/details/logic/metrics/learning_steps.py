# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Learning reviews per card: how many learning answers each card needed before it graduated
(its first review in the Review state), since its last reset (Forget) if it had one: its learning
with the steps it has now.

learning_steps(cfg, deck): {cid: n} of the cards that have graduated, n >= 0 (0: the card
became a review card without learning reviews, e.g. imported with its history cut, or given
a due date).

The counts of the whole collection are read once (one grouped query), then kept: after new
reviews only the cards answered since that had not graduated yet, or were reset, are read again,
as for the Introduced chart (logic.metrics.introduced). A deck is a filter on the cards."""

import threading

from aqt import mw

_LOCK = threading.Lock()
# {"col": id(col), "max_id", "count", "by_card": {cid: n}}
_STATE = {}

# A reset (Forget: a manual entry without interval or ease factor, review_buckets.reset_events).
_RESET = "type = 4 AND factor = 0 AND ivl = 0"
# Learning answers (type 0, rated) after the card's last reset (rid, 0: none) and before its first
# review answer (type 1) since. Cards that graduated to Review (cards.type IN (2, 3)) since their
# last reset are also included even before their first Review-state answer.
_QUERY = f"""
    SELECT g.cid,
           (SELECT COUNT(*) FROM revlog AS r
            WHERE r.cid = g.cid AND r.type = 0 AND r.ease > 0 AND r.id > g.rid
              AND (g.gid IS NULL OR r.id < g.gid))
    FROM (SELECT v.cid, v.rid,
                 (SELECT MIN(x.id) FROM revlog AS x WHERE x.cid = v.cid AND x.type = 1 AND x.id > v.rid) AS gid
          FROM (SELECT cid, MAX(CASE WHEN {_RESET} THEN id ELSE 0 END) AS rid
                FROM revlog /*CIDS*/ GROUP BY cid) AS v) AS g
    WHERE g.gid IS NOT NULL
       OR EXISTS (SELECT 1 FROM cards AS c WHERE c.id = g.cid AND c.type IN (2, 3))
"""


def _full_read():
    return {int(cid): int(n or 0) for cid, n in mw.col.db.all(_QUERY)}


def _refresh_cards(by_card, cids):
    from ....utils import sql_id_list

    cids = [int(c) for c in cids]
    for i in range(0, len(cids), 500):
        chunk = cids[i:i + 500]
        rows = mw.col.db.all(_QUERY.replace("/*CIDS*/", f"WHERE cid IN {sql_id_list(chunk)}"))
        for cid in chunk:
            by_card.pop(cid, None)  # (reset since, not graduated again: no row)
        for cid, n in rows:
            by_card[int(cid)] = int(n or 0)


def _all_counts():
    from .revlog_stamp import revlog_stamp
    max_id, count = revlog_stamp()  # (kept: one read of the history for all the charts)
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
            # Only new reviews: a card already graduated keeps its count; the others answered
            # since are read again, and the cards reset since (their learning starts over).
            by_card = dict(st["by_card"])
            fresh = {int(c) for c in mw.col.db.list("SELECT DISTINCT cid FROM revlog WHERE id > ?", st["max_id"])
                     if int(c) not in by_card}
            fresh |= {int(c) for c in mw.col.db.list(
                f"SELECT DISTINCT cid FROM revlog WHERE id > ? AND {_RESET}", st["max_id"])}
            if fresh:
                _refresh_cards(by_card, fresh)
    if by_card is None:
        by_card = _full_read()
    with _LOCK:
        _STATE.clear()
        _STATE.update({"col": id(mw.col), "max_id": max_id, "count": count, "by_card": by_card})
    return by_card


def learning_distribution(addon_config, deck_id=None, where=""):
    """{"distribution": {n: cards}, "total": cards, "zero": cards at 0, "sum": sum of n} of
    the cards of the decks that have graduated; n >= 1 in the distribution."""
    from ..history_provider import HistoryProvider

    by_card = _all_counts()
    did_limit = HistoryProvider._get_did_limit(addon_config, deck_id)
    # The cards studied as they are now (as Lapses / Reviews per Card): a card reset to new
    # since is left out.
    keep = mw.col.db.list(f"SELECT cards.id FROM cards WHERE cards.type > 0 {did_limit} {where}")
    dist, zero = {}, 0
    for cid in keep:
        n = by_card.get(int(cid))
        if n is None:
            continue  # not graduated yet (new or still learning)
        if n <= 0:
            zero += 1
        else:
            dist[n] = dist.get(n, 0) + 1
    out = {"distribution": dist, "total": sum(dist.values()) + zero, "zero": zero,
           "sum": sum(n * c for n, c in dist.items())}
    return out
