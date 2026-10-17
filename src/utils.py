# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from datetime import datetime, timedelta

from aqt import mw

from .config import ConfigManager
from .const import DEFAULT_ROLLOVER_HOUR, Config

try:
    from anki.consts import REVLOG_RESCHED
except ImportError:
    REVLOG_RESCHED = 4


def sql_id_list(ids) -> str:
    """Format ids as a SQL list: (1, 2, 3)."""
    return "(" + ", ".join(str(int(i)) for i in ids) + ")"


_ROLLOVER_CACHE = [None, 0.0, None]
_ROLLOVER_TTL_S = 2.0


def rollover_hour():
    # get_preferences() serializes the whole preferences protobuf through the
    # Rust backend and was called dozens of times per screen. The rollover hour
    # rarely changes, so it is cached for a few seconds (and re-read after a
    # profile or collection switch).
    try:
        import time as _time

        col = mw.col
        now = _time.monotonic()
        if (
            _ROLLOVER_CACHE[0] is not None
            and _ROLLOVER_CACHE[2] == id(col)
            and now - _ROLLOVER_CACHE[1] < _ROLLOVER_TTL_S
        ):
            return _ROLLOVER_CACHE[0]
        value = col.get_preferences().scheduling.rollover
        _ROLLOVER_CACHE[0] = value
        _ROLLOVER_CACHE[1] = now
        _ROLLOVER_CACHE[2] = id(col)
        return value
    except Exception:
        pass
        
    try:
        if mw.col and mw.col.conf:
            return mw.col.conf.get('rollover', DEFAULT_ROLLOVER_HOUR)
    except Exception:
        pass
        
    return DEFAULT_ROLLOVER_HOUR


def get_rollover_offset_ms():
    """Returns the UTC milliseconds offset for the local rollover hour.
    Makes sure SQL binning (revlog.id - offset) / ms_per_day aligns with logical days.
    """
    off_h = rollover_hour()
    now = datetime.now()
    rollover_dt = now.replace(hour=off_h, minute=0, second=0, microsecond=0)
    return int(rollover_dt.timestamp() * 1000) % 86400000


def get_daystart_epoch_sql(column_name: str, is_ms: bool = True) -> str:
    """
    Generate an SQLite SQL fragment that converts a timestamp column into the 
    unix epoch (in milliseconds) representing the start of the logical day based on the user's rollover hour.
    This correctly handles local timezone rules and daylight saving time shifts worldwide.

    The result is the real instant of local midnight of that logical day (the same value as
    int(datetime(y, m, d).timestamp() * 1000) in Python). Without the final 'utc' modifier
    SQLite returns local midnight written as if it were UTC: turned back into a date with
    datetime.fromtimestamp() it lands on the previous day west of UTC (the Americas), and it
    never matches the day keys built in Python anywhere but in UTC.
    """
    off_h = rollover_hour()
    unixepoch = " 'unixepoch', "
    offset_str = f" '-{off_h} hours', " if off_h else ""
    col_modifier = f"{column_name} / 1000" if is_ms else column_name
    
    return f"(CAST(STRFTIME('%s', {col_modifier}, {unixepoch}{offset_str}'localtime', 'start of day', 'utc') AS INT) * 1000)"


def day_end_with_rollover(date: datetime = None):
    """End of the logical day for a date, shifted by the rollover hour."""
    if date is None:
        date = datetime.today()
    offset = rollover_hour()
    if date.hour < offset:
        date = date - timedelta(days=1)
    return date.replace(hour=23, minute=59, second=59) + timedelta(hours=offset)


_HOME_DECK = "(CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END)"


def split_excluded(excluded):
    """Split the excluded list into (deck ids, deleted cards excluded).

    The list holds deck ids and may also hold the string "deleted" (Deleted Cards row).
    """
    ids = []
    deleted = False
    for x in (excluded or []):
        if isinstance(x, str) and x == "deleted":
            deleted = True
            continue
        try:
            ids.append(int(x))
        except (TypeError, ValueError):
            continue
    return ids, deleted


def excluded_not_in_clause(excluded):
    """SQL clause (starts with AND) leaving out excluded decks and, if listed, deleted cards."""
    ids, deleted = split_excluded(excluded)
    if ids and deleted:
        return f"AND ({_HOME_DECK} NOT IN {sql_id_list(ids)} AND {_HOME_DECK} IS NOT NULL)"
    if ids:
        return f"AND ({_HOME_DECK} NOT IN {sql_id_list(ids)} OR {_HOME_DECK} IS NULL)"
    if deleted:
        return f"AND {_HOME_DECK} IS NOT NULL"
    return ""


def excluded_decks_clause(excluded_dids: list = None):
    """SQL clause (starts with AND) that leaves out the excluded decks.

    A card in a filtered deck counts for its home deck. On the deck overview
    only the current deck and its children are kept. Returns '' when nothing
    is excluded or when lifetime stats are on in the browser.
    """
    if not excluded_dids:
        return ''
    conf = ConfigManager(mw).config
    if conf.get(Config.BROWSER_LIFETIME_STATS, False) and mw.state != 'overview':
        return ''
    excluded_ids, deleted_excluded = split_excluded(excluded_dids)
    keep_deleted = (
        conf.get(Config.INCLUDE_DELETED_CARDS, False)
        and mw.state != 'overview'
        and not deleted_excluded
    )
    if keep_deleted:
        # Reviews of deleted cards have no deck, and NOT IN would drop them.
        return excluded_not_in_clause(excluded_ids)
    if mw.state == 'overview':
        pool = mw.col.decks.deck_and_child_ids(mw.col.decks.current().get('id'))
    else:
        pool = [d.id for d in mw.col.decks.all_names_and_ids()]
    kept = [d for d in pool if d not in excluded_ids]
    return f'AND {_HOME_DECK} IN {sql_id_list(kept)}'


def format_hours(hours: float, precision: int = None, use_decimal=True, hrs_text="", min_text=""):
    """Format a duration given in hours.

    Decimal mode shows hours above 1 and minutes below. Otherwise h:mm, or m:ss
    under an hour. hrs_text and min_text are optional unit suffixes.
    """
    if precision is None:
        from .details.widgets.chart_utils.formatting import stats_precision
        precision = stats_precision()

    if use_decimal:
        from .details.widgets.chart_utils.formatting import fmt_num
        if hours == 0:
            return f"0 {min_text}" if min_text else "0"
        if hours > 1:
            value, unit = fmt_num(hours, precision), hrs_text
        else:
            value, unit = fmt_num(hours * 60, precision), min_text
        return f"{value} {unit}" if unit else str(value)

    total_seconds = int(round(hours * 3600))
    if hours > 1:
        return f"{total_seconds // 3600}:{total_seconds % 3600 // 60:02d}"
    return f"{total_seconds // 60}:{total_seconds % 60:02d}"


def excluded_day_rules():
    """Excluded dates as (start_ms, end_ms, deck_ids) rules; deck_ids None means all decks.

    The setting holds entries that are either 'YYYY-MM-DD' / 'YYYY-MM-DD..YYYY-MM-DD'
    (all decks) or {"dates": <same text>, "decks": [deck ids]}. A day starts at the
    rollover hour. Bad entries are ignored.
    """
    try:
        raw = ConfigManager(mw).config.get(Config.EXCLUDED_DATES, []) or []
    except Exception:
        return []
    off_h = rollover_hour()
    out = []
    for entry in raw:
        try:
            decks = None
            if isinstance(entry, dict):
                text = entry.get("dates", "")
                ids = [int(x) for x in (entry.get("decks") or [])]
                decks = ids or None
            else:
                text = entry
            first, _, last = str(text).strip().partition("..")
            d1 = datetime.strptime(first.strip(), "%Y-%m-%d")
            d2 = datetime.strptime(last.strip(), "%Y-%m-%d") if last.strip() else d1
            if d2 < d1:
                d1, d2 = d2, d1
            start = d1.replace(hour=off_h)
            end = (d2 + timedelta(days=1)).replace(hour=off_h)
            out.append((int(start.timestamp() * 1000), int(end.timestamp() * 1000), decks))
        except Exception:
            continue
    return out


def excluded_days_need_cards():
    """True when a rule is limited to decks, so the query must join `cards`."""
    return any(r[2] for r in excluded_day_rules())


def excluded_days_clause(column="revlog.id"):
    """SQL clause (starts with AND) that leaves out reviews done on excluded dates.

    `column` is the revlog id column (ms timestamp, or seconds on old data).
    Rules limited to decks use the home deck of `cards`, which the query must join.
    Returns '' when no date is excluded.
    """
    rules = excluded_day_rules()
    if not rules:
        return ""
    ms = f"(CASE WHEN {column} > 1000000000000 THEN {column} ELSE {column} * 1000 END)"
    parts = []
    for a, b, decks in rules:
        cond = f"({ms} >= {a} AND {ms} < {b})"
        if decks:
            try:
                ids = set()
                for d in decks:
                    ids.update(mw.col.decks.deck_and_child_ids(d))
                ids = sorted(ids) or list(decks)
            except Exception:
                ids = list(decks)
            cond = f"({cond} AND COALESCE({_HOME_DECK} IN {sql_id_list(ids)}, 0))"
        parts.append(cond)
    return f"AND NOT ({' OR '.join(parts)})"

