# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Time per card: the time spent on each card over all its reviews.

The times of the whole collection are read once (one grouped query of the review history),
then kept: after new reviews only the cards answered since are summed again, as for Learning
Steps per Card (logic.metrics.learning_steps). A deck is a filter on the cards."""

import threading

from aqt import mw

_LOCK = threading.Lock()
# {"col": id(col), "max_id", "count", "by_card": {cid: ms}}
_STATE = {}

MAX_SECONDS = 3600  # cards of an hour or more in the last bar

_QUERY = "SELECT cid, SUM(time) FROM revlog {where} GROUP BY cid"


def _all_times():
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
            # Only new reviews: the cards answered since are summed again.
            from ....utils import sql_id_list

            by_card = dict(st["by_card"])
            cids = [int(c) for c in mw.col.db.list("SELECT DISTINCT cid FROM revlog WHERE id > ?", st["max_id"])]
            for i in range(0, len(cids), 500):
                chunk = cids[i:i + 500]
                for cid, ms in mw.col.db.all(_QUERY.format(where=f"WHERE cid IN {sql_id_list(chunk)}")):
                    by_card[int(cid)] = int(ms or 0)
    if by_card is None:
        by_card = {int(cid): int(ms or 0) for cid, ms in mw.col.db.all(_QUERY.format(where=""))}
    with _LOCK:
        _STATE.clear()
        _STATE.update({"col": id(mw.col), "max_id": max_id, "count": count, "by_card": by_card})
    return by_card


def time_distribution(addon_config, deck_id=None, where=""):
    """{"distribution": {seconds: cards}, "total": cards, "zero": 0, "sum": seconds} of the cards
    already studied (not new) of the decks, as Lapses / Reviews per Card. Seconds from 1 (a card
    answered in under a second is in the first bar) to MAX_SECONDS; "sum" is the real time."""
    from ..history_provider import HistoryProvider

    by_card = _all_times()
    did_limit = HistoryProvider._get_did_limit(addon_config, deck_id)
    dist, total_ms = {}, 0
    for cid in mw.col.db.list(f"SELECT cards.id FROM cards WHERE cards.type > 0 {did_limit} {where}"):
        ms = by_card.get(int(cid))
        if not ms or ms <= 0:
            continue  # no timed answer (imported without its history, a due date set by hand)
        n = min(MAX_SECONDS, max(1, int(round(ms / 1000.0))))
        dist[n] = dist.get(n, 0) + 1
        total_ms += ms
    return {"distribution": dist, "total": sum(dist.values()), "zero": 0, "sum": total_ms / 1000.0}
