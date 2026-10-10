# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Open the Anki browser for the data behind a chart bar (like the native stats)."""
from ....utils import excluded_days_clause
import re
from datetime import datetime

from aqt import mw

from .. import ConfigManager, rollover_hour
from ..logger import log_error

_MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}
_DAY_RE = re.compile(r"^([A-Z][a-z]{2}) (\d{1,2}), (\d{4})$")
_TIME_RE = re.compile(r"^([A-Z][a-z]{2}) (\d{1,2}), (\d{1,2}):(\d{2})$")
HI_RES_BIN_SECONDS = 600


def is_deleted_selection(deck):
    if deck == -1:
        return True
    return isinstance(deck, list) and "deleted" in deck


def _deck_names(deck):
    if isinstance(deck, int) and deck > 0:
        try:
            return [mw.col.decks.name(deck)]
        except Exception:
            return []
    if isinstance(deck, str):
        if deck.isdigit():
            return _deck_names(int(deck))
        return [deck] if deck else []
    if isinstance(deck, list):
        names = []
        for d in deck:
            if isinstance(d, (int, str)) and d != "deleted":
                names.extend(_deck_names(d))
        return names
    return []


def deck_clause(deck):
    names = _deck_names(deck)
    if not names:
        return ""
    parts = ['deck:"%s"' % n.replace('"', '\\"') for n in names]
    return parts[0] if len(parts) == 1 else "(" + " or ".join(parts) + ")"


def _parse_one(label, end):
    """Return the start (or end) of a bar label in epoch ms, or None."""
    label = label.strip()
    now = datetime.now()
    m = _DAY_RE.match(label)
    if m and m.group(1) in _MONTHS:
        dt = datetime(int(m.group(3)), _MONTHS[m.group(1)], int(m.group(2)))
        start = int((dt.timestamp() + rollover_hour() * 3600) * 1000)
        return start + 86400000 if end else start
    m = _TIME_RE.match(label)
    if m and m.group(1) in _MONTHS:
        year = now.year
        dt = datetime(year, _MONTHS[m.group(1)], int(m.group(2)), int(m.group(3)), int(m.group(4)))
        if dt > now:
            dt = dt.replace(year=year - 1)
        start = int(dt.timestamp() * 1000)
        return start + HI_RES_BIN_SECONDS * 1000 if end else start
    return None


def label_to_range_ms(label):
    if not label:
        return None
    parts = str(label).split(" - ")
    try:
        start = _parse_one(parts[0], end=False)
        end = _parse_one(parts[-1], end=True)
    except Exception:
        return None
    if start is None or end is None or end <= start:
        return None
    return start, end


def _tip(text):
    from aqt.utils import tooltip
    tooltip(text)


def open_search(terms):
    from aqt import dialogs
    browser = dialogs.open("Browser", mw)
    browser.search_for_terms(terms)


def open_query(query, deck):
    """Open the browser on a plain search string, limited to the deck selection."""
    if is_deleted_selection(deck):
        _tip("Deleted cards cannot be shown in the browser")
        return
    clause = deck_clause(deck)
    open_search(" ".join(p for p in (query, clause) if p))


def _fetch_cids(kind, start_ms, end_ms, deck):
    try:
        from ..history_provider import HistoryProvider
        cfg = ConfigManager(mw)
        did_limit = HistoryProvider._get_did_limit(cfg, deck)
        if kind == "added":
            sql = (f"SELECT cards.id FROM cards WHERE cards.id >= {start_ms} AND cards.id < {end_ms} "
                   f"{did_limit}")
        else:
            s_sec, e_sec = start_ms // 1000, end_ms // 1000
            sql = (
                "SELECT DISTINCT cards.id FROM revlog JOIN cards ON revlog.cid = cards.id WHERE "
                f"((revlog.id >= {start_ms} AND revlog.id < {end_ms}) "
                f"OR (revlog.id >= {s_sec} AND revlog.id < {e_sec})) {did_limit} {excluded_days_clause()}"
            )
        return mw.col.db.list(sql)
    except Exception as e:
        import traceback
        log_error(f"browser_search fetch failed: {e}\n{traceback.format_exc()}")
        return []


def open_cards_for_range(kind, start_ms, end_ms, deck):
    """kind: 'reviewed' (cards with a review in the range) or 'added' (cards created in it)."""
    if is_deleted_selection(deck):
        _tip("Deleted cards cannot be shown in the browser")
        return

    def _done(fut):
        try:
            cids = fut.result()
        except Exception as e:
            log_error(f"browser_search result failed: {e}")
            return
        if not cids:
            _tip("No cards found")
            return
        clause = deck_clause(deck)
        terms = "cid:" + ",".join(str(c) for c in cids)
        open_search(" ".join(p for p in (terms, clause) if p))

    mw.taskman.run_in_background(lambda: _fetch_cids(kind, start_ms, end_ms, deck), on_done=_done)


def open_cards_for_label(kind, label, deck):
    rng = label_to_range_ms(label)
    if rng is None:
        return False
    open_cards_for_range(kind, rng[0], rng[1], deck)
    return True


def _fetch_hour_cids(hour, span, deck):
    try:
        from ..history_provider import HistoryProvider
        from ..data.core.time_utils import get_time_range_ms
        from .. import Period
        cfg = ConfigManager(mw)
        did_limit = HistoryProvider._get_did_limit(cfg, deck)
        start_ms, end_ms, _, _ = get_time_range_ms(span, week_start=cfg.config.get("week_start", 0))
        ms = "(CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END)"
        limit = ""
        if start_ms > 0:
            limit += f" AND {ms} >= {int(start_ms)}"
        if end_ms > 0 and span != Period.TOTAL:
            limit += f" AND {ms} < {int(end_ms)}"
        sql = (
            "SELECT DISTINCT cards.id FROM revlog JOIN cards ON revlog.cid = cards.id "
            "WHERE revlog.type < 4 AND CAST(strftime('%H', "
            "CASE WHEN revlog.id > 1000000000000 THEN revlog.id / 1000.0 ELSE revlog.id END, "
            f"'unixepoch', 'localtime') AS INTEGER) = {int(hour)} {did_limit} {excluded_days_clause()} {limit}"
        )
        return mw.col.db.list(sql)
    except Exception as e:
        import traceback
        log_error(f"browser_search hour fetch failed: {e}\n{traceback.format_exc()}")
        return []


def open_cards_for_hour(hour, span, deck):
    """Cards reviewed during a given hour of the day, inside the chart's period."""
    if is_deleted_selection(deck):
        _tip("Deleted cards cannot be shown in the browser")
        return

    def _done(fut):
        try:
            cids = fut.result()
        except Exception as e:
            log_error(f"browser_search result failed: {e}")
            return
        if not cids:
            _tip("No cards found")
            return
        terms = "cid:" + ",".join(str(c) for c in cids)
        clause = deck_clause(deck)
        open_search(" ".join(p for p in (terms, clause) if p))

    mw.taskman.run_in_background(lambda: _fetch_hour_cids(hour, span, deck), on_done=_done)


def open_card(cid):
    open_search(f"cid:{int(cid)}")
