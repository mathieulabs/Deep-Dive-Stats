# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Open the Anki browser for the data behind a chart bar (like the native stats)."""
from ....utils import excluded_days_clause
import re
from datetime import datetime, timedelta

from aqt import mw

from .. import ConfigManager, rollover_hour
from ..logger import log_error
from ....i18n import tr

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
    parts = ['deck:"%s"' % n.replace('\\', '\\\\').replace('"', '\\"') for n in names]
    return parts[0] if len(parts) == 1 else "(" + " or ".join(parts) + ")"


def _parse_one(label, end):
    """Return the start (or end) of a bar label in epoch ms, or None."""
    label = label.strip()
    now = datetime.now()
    m = _DAY_RE.match(label)
    if m and m.group(1) in _MONTHS:
        # The Anki day runs from its rollover hour to the next day's, local time (23 or 25
        # hours on the day of a clock change).
        dt = datetime(int(m.group(3)), _MONTHS[m.group(1)], int(m.group(2)), rollover_hour())
        if end:
            dt += timedelta(days=1)
        return int(dt.timestamp() * 1000)
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
        _tip(tr("Deleted cards cannot be shown in the browser"))
        return
    clause = deck_clause(deck)
    q = (query or "").strip()
    if q and clause:
        open_search(f"({q}) {clause}")
    else:
        open_search(q or clause)


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
        _tip(tr("Deleted cards cannot be shown in the browser"))
        return

    def _done(fut):
        try:
            cids = fut.result()
        except Exception as e:
            log_error(f"browser_search result failed: {e}")
            return
        if not cids:
            _tip(tr("No cards found"))
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
        _tip(tr("Deleted cards cannot be shown in the browser"))
        return

    def _done(fut):
        try:
            cids = fut.result()
        except Exception as e:
            log_error(f"browser_search result failed: {e}")
            return
        if not cids:
            _tip(tr("No cards found"))
            return
        terms = "cid:" + ",".join(str(c) for c in cids)
        clause = deck_clause(deck)
        open_search(" ".join(p for p in (terms, clause) if p))

    mw.taskman.run_in_background(lambda: _fetch_hour_cids(hour, span, deck), on_done=_done)


def open_card(cid):
    open_search(f"cid:{int(cid)}")


# The kinds of a review, as the charts count them: Answer Buttons' groups (by the review's type) and the kinds of the
# charts by kind (First Answer Retention, Answer Time: review_buckets._KIND, learning by its interval too)
_BTN_KIND = {
    "learning": "revlog.type IN (0, 2)",
    "young": "revlog.type = 1 AND revlog.lastIvl < 21",
    "mature": "revlog.type = 1 AND revlog.lastIvl >= 21",
}
_KIND = {
    "learn": "(revlog.type IN (0, 2) OR revlog.lastIvl <= 0)",
    "young": "(revlog.type NOT IN (0, 2) AND revlog.lastIvl > 0 AND revlog.lastIvl < 21)",
    "mature": "(revlog.type NOT IN (0, 2) AND revlog.lastIvl >= 21)",
    "review": "(revlog.type NOT IN (0, 2) AND revlog.lastIvl > 0)",  # young and mature (a chart's card type filter)
}


def _int_pair(v):
    try:
        a, b = v
        return int(a), int(b)
    except Exception:
        return None


def reviews_sql(spec, start_ms, end_ms, limit):
    """The cards with an answer in [start_ms, end_ms) matching spec (a click on a chart of reviews):
        weekday 0 Monday .. 6 Sunday, hour 0-23 (the clock of this computer, as Week by Hour and Hourly count them),
        ease 1-4, btn_kind learning / young / mature (Answer Buttons), kind learn / young / mature / review (by interval),
        secs [a, b) (answer time in seconds, a minute or more counted as 60), ivl [a, b) (interval before the answer),
        first (the first answer of the card on its day: First Answer Retention), passed true / false,
        lapse (Again on a review card: Forgotten), introduced (the card's first answer, or its first after a reset),
        reset (a reset itself, Forget: not an answer; Reset Cards)."""
    from ..metrics.review_buckets import MAX_INTERVAL, MAX_SECONDS, _join

    local = "revlog.id / 1000, 'unixepoch', 'localtime'"
    w = [f"revlog.id >= {int(start_ms)}", f"revlog.id < {int(end_ms)}"]
    if spec.get("reset"):
        w.append("revlog.type = 4 AND revlog.factor = 0 AND revlog.ivl = 0")  # (review_buckets.reset_events)
    else:
        w += ["revlog.type < 4", "revlog.ease BETWEEN 1 AND 4"]
    if spec.get("hour") is not None:
        w.append(f"CAST(strftime('%H', {local}) AS INTEGER) = {int(spec['hour'])}")
    if spec.get("weekday") is not None:
        # strftime('%w'): 0 is Sunday
        w.append(f"(CAST(strftime('%w', {local}) AS INTEGER) + 6) % 7 = {int(spec['weekday'])}")
    if spec.get("ease") is not None:
        w.append(f"revlog.ease = {int(spec['ease'])}")
    if spec.get("btn_kind") in _BTN_KIND:
        w.append(_BTN_KIND[spec["btn_kind"]])
    if spec.get("kind") in _KIND:
        w.append(_KIND[spec["kind"]])
    secs = _int_pair(spec.get("secs"))
    if secs:
        w.append(f"MIN(revlog.time / 1000, {MAX_SECONDS}) >= {secs[0]} AND MIN(revlog.time / 1000, {MAX_SECONDS}) < {secs[1]}")
    ivl = _int_pair(spec.get("ivl"))
    if ivl:
        w.append(f"MIN(revlog.lastIvl, {MAX_INTERVAL}) >= {ivl[0]} AND MIN(revlog.lastIvl, {MAX_INTERVAL}) < {ivl[1]}")
    if spec.get("passed") is not None:
        w.append("revlog.ease > 1" if spec["passed"] else "revlog.ease = 1")
    if spec.get("lapse"):
        w.append("revlog.type = 1 AND revlog.ease = 1")
    if spec.get("first"):
        # the first answer of its card on its day of Anki (review_buckets.first_answers)
        cutoff = int(mw.col.sched.day_cutoff)
        base = cutoff - 86400 * 40000
        w.append(f"""revlog.id IN (SELECT MIN(id) FROM revlog
                     WHERE id >= {int(start_ms)} AND id < {int(end_ms)} AND type < 4 AND ease BETWEEN 1 AND 4
                     GROUP BY cid, (id / 1000 - {base}) / 86400)""")
    if spec.get("introduced"):
        # no rated answer before it, unless a reset ("Forget": a manual entry without ease factor) came between;
        # cramming answers (Filtered, no ease factor) neither introduce nor count before (metrics.introduced)
        w.append("NOT (revlog.type = 3 AND revlog.factor = 0)")
        w.append("""NOT EXISTS (SELECT 1 FROM revlog AS p WHERE p.cid = revlog.cid AND p.id < revlog.id
                     AND p.type < 4 AND p.ease > 0 AND NOT (p.type = 3 AND p.factor = 0)
                     AND NOT EXISTS (SELECT 1 FROM revlog AS z WHERE z.cid = revlog.cid AND z.type = 4
                                     AND z.factor = 0 AND z.id > p.id AND z.id < revlog.id))""")
    return f"SELECT DISTINCT revlog.cid FROM revlog {_join(limit) or 'LEFT JOIN cards ON revlog.cid = cards.id'} WHERE {' AND '.join(w)} {excluded_days_clause()} {limit or ''}"


def _span_range(span):
    from ..data.core.time_utils import get_time_range_ms
    from .. import Period

    cfg = ConfigManager(mw)
    start_ms, end_ms, _, _ = get_time_range_ms(span, week_start=cfg.config.get("week_start", 0))
    if span == Period.TOTAL or end_ms <= 0:
        end_ms = (int(mw.col.sched.day_cutoff) + 86400) * 1000
    return max(0, int(start_ms)), int(end_ms)


def open_reviews(spec, span, deck):
    """A click on a chart of reviews: the cards answered as spec says (reviews_sql), in spec's range (ms: [start, end],
    label: a bar's date, else the chart's period span)."""
    from ..metrics.review_buckets import did_limit

    if is_deleted_selection(deck):
        _tip(tr("Deleted cards cannot be shown in the browser"))
        return
    rng = _int_pair(spec.get("ms"))
    if not rng and spec.get("label"):
        rng = label_to_range_ms(spec["label"])
    if not rng:
        rng = _span_range(int(span))

    def work():
        try:
            cfg = ConfigManager(mw)
            sql = reviews_sql(spec, rng[0], rng[1], did_limit(cfg, deck, False))
            cids = mw.col.db.list(sql)
            if isinstance(spec.get("searches"), list):
                # Custom Bar: only the cards its searches find (as it counts them, metrics.custom_search; a search
                # Anki cannot read finds none)
                from ..metrics.custom_search import matching

                sets, _cards = matching(cfg, deck, False, [str(q or "") for q in spec["searches"]])
                found = set().union(*[s for s in sets if s])
                cids = [c for c in cids if int(c) in found]
            return cids
        except Exception as e:
            import traceback
            log_error(f"browser_search reviews failed: {e}\n{traceback.format_exc()}")
            return []

    def _done(fut):
        try:
            cids = fut.result()
        except Exception as e:
            log_error(f"browser_search result failed: {e}")
            return
        if not cids:
            _tip(tr("No cards found"))
            return
        clause = deck_clause(deck)
        open_search(" ".join(p for p in ("cid:" + ",".join(str(c) for c in cids), clause) if p))

    mw.taskman.run_in_background(work, on_done=_done)
