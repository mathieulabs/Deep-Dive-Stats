# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Anki search-query filtering (e.g. 'tag:kanji', 'flag:1', 'prop:lapses>3').

Queries are resolved on the main thread via Anki's native `mw.col.find_cards(query)`
and cached by `(normalized_query, db_stamp)`. Background worker threads activate a
resolved query inside `with search_scope(query):` without ever calling `mw.col.find_cards`
off the main thread.

When no query is active (empty string), every helper is a zero-cost no-op so
`GlobalHistoryCache` and all existing code paths run completely untouched.
"""

from contextlib import contextmanager
import threading

from aqt import mw

_LOCAL = threading.local()
_LOCK = threading.Lock()
_CACHE = {}  # (query, col_id, stamp) -> tuple[int, ...]
_MAX_CACHE = 48
_CHUNK_SIZE = 4000  # split huge ID lists into clean OR-ed IN(...) chunks


def normalize_query(query):
    """Canonical trimmed search string ('' when none)."""
    return str(query or "").strip()


def _db_stamp():
    """Lightweight collection stamp that changes whenever cards/notes are added, edited, or deleted."""
    try:
        col = getattr(mw, "col", None)
        if col is None:
            return None
        row = col.db.first("SELECT count(), max(id), total(mod) FROM cards")
        n_mod = col.db.scalar("SELECT total(mod) FROM notes")
        return (id(col), tuple(row or ()), n_mod)
    except Exception:
        return None


def resolve_search(query):
    """Resolve an Anki search query on the main thread.

    Returns `(cids_tuple, error_message)`:
    - Empty query -> `(None, None)` (no filter active)
    - Valid query -> `(tuple_of_int_cids, None)`
    - Invalid syntax / error -> `(None, str(err))`
    """
    q = normalize_query(query)
    if not q:
        return None, None
    col = getattr(mw, "col", None)
    if col is None:
        return (), None

    stamp = _db_stamp()
    key = (q, stamp)
    if stamp is not None:
        with _LOCK:
            hit = _CACHE.get(key)
        if hit is not None:
            return hit, None

    try:
        raw = col.find_cards(q)
        cids = tuple(int(c) for c in raw)
    except Exception as exc:
        msg = str(exc).strip() or exc.__class__.__name__
        # Strip noisy Rust backtrace / prefix if present
        if "\n" in msg:
            msg = msg.splitlines()[0].strip()
        return None, msg

    if stamp is not None:
        with _LOCK:
            if len(_CACHE) >= _MAX_CACHE:
                _CACHE.clear()
            _CACHE[key] = cids
    return cids, None


def cached_cids(query):
    """Return cached `(cids_tuple, found)` for a query without invoking `find_cards`.
    Safe to call from any thread."""
    q = normalize_query(query)
    if not q:
        return None, True
    stamp = _db_stamp()
    if stamp is not None:
        with _LOCK:
            hit = _CACHE.get((q, stamp))
        if hit is not None:
            return hit, True
    # Fallback: most recent entry for this query in the same collection
    col_id = id(getattr(mw, "col", None))
    with _LOCK:
        for (cq, cstamp), cids in reversed(list(_CACHE.items())):
            if cq == q and cstamp and cstamp[0] == col_id:
                return cids, True
    return None, False


def _current():
    stack = getattr(_LOCAL, "stack", None)
    return stack[-1] if stack else None


def has_active_search():
    """True when the current thread is inside an active non-empty `search_scope`."""
    return _current() is not None


def active_search_query():
    """Normalized active search query for the current thread, or ''."""
    cur = _current()
    return cur[0] if cur else ""


def active_card_clause(alias="cards"):
    """SQL `AND ...` clause restricting `alias.id` to the active search's matching cards.

    Returns `''` when no search filter is active on the current thread.
    """
    cur = _current()
    if cur is None:
        return ""
    cids = cur[1]
    if not cids:
        return "AND 1=0"
    col_expr = f"{alias}.id" if alias else "id"
    if len(cids) <= _CHUNK_SIZE:
        return f"AND {col_expr} IN ({','.join(map(str, cids))})"
    parts = [
        f"{col_expr} IN ({','.join(map(str, cids[i:i + _CHUNK_SIZE]))})"
        for i in range(0, len(cids), _CHUNK_SIZE)
    ]
    return f"AND ({' OR '.join(parts)})"


@contextmanager
def search_scope(query, cids=None):
    """Activate an Anki search filter for the current thread.

    If `query` is empty, acts as a no-op (preserving any outer scope as None if nested with '').
    If `cids` is not supplied, looks up the pre-resolved cache (or resolves on main thread).
    """
    q = normalize_query(query)
    if not q:
        yield
        return

    resolved = cids
    if resolved is None:
        resolved, found = cached_cids(q)
        if not found:
            if threading.current_thread() is threading.main_thread():
                resolved, err = resolve_search(q)
                if err is not None:
                    resolved = ()
            else:
                resolved = ()

    stack = getattr(_LOCAL, "stack", None)
    if stack is None:
        stack = _LOCAL.stack = []
    stack.append((q, tuple(resolved or ())))
    try:
        yield
    finally:
        stack.pop()
