# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""(last review id, review count): the stamp the history stores and caches of the charts compare to
know whether reviews were added or deleted since they were read.

The count reads the whole review history (an index scan): each store and cache asked it again, a
dozen times when Deep Dive or the pinned widgets load. It is now read once and kept until the
collection changes (an operation such as an answer or an undo, a sync, another collection), and at
most _TTL seconds, for the changes made without an operation (another add-on, Check Database)."""

import threading
import time

from aqt import mw

_TTL = 2.0
_LOCK = threading.Lock()
_KEPT = {}  # {"col": id of the collection, "at": time.monotonic(), "stamp": (max id, count)}
_GEN = [0]  # bumped by each change: a stamp read across a change is not kept
_HOOKED = [False]


def drop(*_args, **_kwargs):
    """Forgets the stamp kept (an Anki hook: any arguments)."""
    with _LOCK:
        _KEPT.clear()
        _GEN[0] += 1


def _hook():
    with _LOCK:
        if _HOOKED[0]:
            return
        _HOOKED[0] = True
    try:
        from aqt import gui_hooks

        for name in ("operation_did_execute", "reviewer_did_answer_card", "sync_did_finish", "collection_did_load"):
            hook = getattr(gui_hooks, name, None)
            if hook is not None:
                hook.append(drop)
    except Exception:
        from ..logger import log_swallowed

        log_swallowed()


def revlog_stamp():
    """(the last review id, the number of reviews), 0 for none. Raises as the query would (no collection)."""
    _hook()
    col = id(mw.col)
    with _LOCK:
        kept, gen = dict(_KEPT), _GEN[0]
    now = time.monotonic()
    if kept.get("col") == col and now - kept["at"] < _TTL:
        return kept["stamp"]
    row = mw.col.db.first("SELECT max(id), count() FROM revlog") or (None, 0)
    stamp = (int(row[0] or 0), int(row[1] or 0))
    with _LOCK:
        if _GEN[0] == gen:
            _KEPT.update(col=col, at=now, stamp=stamp)
    return stamp
