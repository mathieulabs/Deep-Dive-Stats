# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .....utils import excluded_days_clause
from ..shared import Config, REVLOG_RESCHED, Period, get_daystart_epoch_sql, mw
from ...logger import log_swallowed
from ...data.core.revlog_slices import revlog_slices as _revlog_slices, sliced_all as _sliced_all

def _deleted_cards_count(slices):
    """Reviewed cards that no longer exist, counted once each across the slices."""
    cids = set()
    for part in slices:
        cids.update(mw.col.db.list(f"""
            SELECT DISTINCT revlog.cid
            FROM revlog
            LEFT JOIN cards ON revlog.cid = cards.id
            WHERE cards.id IS NULL {part}
        """))
    return len(cids)


def fetch_all_decks_context(provider_cls, addon_config, range_type=Period.YEAR, min_rev_id=None, min_card_id=None):
    """Fetch all history and counts for all decks in one go.
    If min_rev_id or min_card_id is provided, only fetches new records since that ID (Delta Update).
    """
    is_delta = min_rev_id is not None or min_card_id is not None
    from ...data.core.time_utils import get_time_range_ms
    from ...logger import log_debug
    log_debug("HistoryProvider: fetch_all_decks_context started (Bulk Cache Build)", tag="CACHE")

    week_start = addon_config.config.get(Config.WEEK_START, 0)

    start_ms, end_ms, _, _ = get_time_range_ms(range_type, week_start=week_start)

    rev_start_ms = start_ms
    card_start_ms = start_ms

    if range_type == Period.TOTAL and not is_delta:
        rev_start_ms = mw.col.db.scalar("SELECT MIN(id) FROM revlog WHERE id > 0") or 0
        card_start_ms = mw.col.db.scalar("SELECT MIN(id) FROM cards WHERE id > 0") or 0
    else:
        if min_rev_id is not None:
             rev_start_ms = max(start_ms, min_rev_id if min_rev_id > 1000000000000 else min_rev_id * 1000)

        if min_card_id is not None:
             card_start_ms = max(start_ms, min_card_id if min_card_id > 1000000000000 else min_card_id * 1000)

    delta_filter = f"AND revlog.id > {min_rev_id}" if min_rev_id is not None else ""
    delta_filter = f"{delta_filter} {excluded_days_clause()}"
    delta_filter_added = f"AND id > {min_card_id}" if min_card_id is not None else ""

    # A delta reads a few new reviews in one go; a full build reads the revlog in slices.
    slices = [""] if is_delta else _revlog_slices()

    # Warm up the global deleted count in this background thread
    deleted_cards_count = None
    if not hasattr(provider_cls, "_session_deleted_count"):
        deleted_cards_count = _deleted_cards_count(slices)
        provider_cls._session_deleted_count = deleted_cards_count

    # Handle both seconds (pre-2020) and milliseconds (modern)
    def query_rev(part):
        return f"""
        SELECT 
            COALESCE((CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END), -1) as hdid,
            {get_daystart_epoch_sql('CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END', is_ms=True)} as bin_idx,
            COUNT(*) as reviews,
            COALESCE(SUM(revlog.time), 0) as time_ms,
            COALESCE(SUM(CASE WHEN revlog.ease > 1 THEN 1 ELSE 0 END), 0) as passed,
            COALESCE(SUM(CASE WHEN revlog.ease > 0 AND NOT (revlog.type = 3 AND revlog.factor = 0) AND (revlog.type = 1 OR revlog.lastIvl <= -86400 OR revlog.lastIvl >= 1) AND revlog.lastIvl < 21 THEN 1 ELSE 0 END), 0) as rev_young,
            COALESCE(SUM(CASE WHEN revlog.ease > 0 AND NOT (revlog.type = 3 AND revlog.factor = 0) AND (revlog.type = 1 OR revlog.lastIvl <= -86400 OR revlog.lastIvl >= 1) AND revlog.lastIvl < 21 AND revlog.ease > 1 THEN 1 ELSE 0 END), 0) as pass_young,
            COALESCE(SUM(CASE WHEN revlog.ease > 0 AND NOT (revlog.type = 3 AND revlog.factor = 0) AND (revlog.type = 1 OR revlog.lastIvl <= -86400 OR revlog.lastIvl >= 1) AND revlog.lastIvl >= 21 THEN 1 ELSE 0 END), 0) as rev_mat,
            COALESCE(SUM(CASE WHEN revlog.ease > 0 AND NOT (revlog.type = 3 AND revlog.factor = 0) AND (revlog.type = 1 OR revlog.lastIvl <= -86400 OR revlog.lastIvl >= 1) AND revlog.lastIvl >= 21 AND revlog.ease > 1 THEN 1 ELSE 0 END), 0) as pass_mat,
            COALESCE(SUM(CASE WHEN revlog.type = 0 THEN 1 ELSE 0 END), 0) as learn_count,
            COALESCE(SUM(CASE WHEN revlog.type = 2 THEN 1 ELSE 0 END), 0) as relearn_count,
            COALESCE(SUM(CASE WHEN revlog.type = 1 AND revlog.lastIvl < 21 THEN 1 ELSE 0 END), 0) as young_count,
            COALESCE(SUM(CASE WHEN revlog.type = 1 AND revlog.lastIvl >= 21 THEN 1 ELSE 0 END), 0) as mature_count,
            COALESCE(SUM(CASE WHEN revlog.type = 3 THEN 1 ELSE 0 END), 0) as cram_count,
            COALESCE(SUM(CASE WHEN revlog.type = 0 THEN revlog.time ELSE 0 END), 0) as learn_time_ms,
            COALESCE(SUM(CASE WHEN revlog.type = 2 THEN revlog.time ELSE 0 END), 0) as relearn_time_ms,
            COALESCE(SUM(CASE WHEN revlog.type = 1 AND revlog.lastIvl < 21 THEN revlog.time ELSE 0 END), 0) as young_time_ms,
            COALESCE(SUM(CASE WHEN revlog.type = 1 AND revlog.lastIvl >= 21 THEN revlog.time ELSE 0 END), 0) as mature_time_ms,
            COALESCE(SUM(CASE WHEN revlog.type = 3 THEN revlog.time ELSE 0 END), 0) as cram_time_ms,
            COALESCE(SUM(CASE WHEN revlog.ease = 1 THEN 1 ELSE 0 END), 0) as count_again,
            COALESCE(SUM(CASE WHEN revlog.ease = 2 THEN 1 ELSE 0 END), 0) as count_hard,
            COALESCE(SUM(CASE WHEN revlog.ease = 3 THEN 1 ELSE 0 END), 0) as count_good,
            COALESCE(SUM(CASE WHEN revlog.ease = 4 THEN 1 ELSE 0 END), 0) as count_easy,
            
            COALESCE(SUM(CASE WHEN revlog.type IN (0, 2) AND revlog.ease = 1 THEN 1 ELSE 0 END), 0) as learn_btn1,
            COALESCE(SUM(CASE WHEN revlog.type IN (0, 2) AND revlog.ease = 2 THEN 1 ELSE 0 END), 0) as learn_btn2,
            COALESCE(SUM(CASE WHEN revlog.type IN (0, 2) AND revlog.ease = 3 THEN 1 ELSE 0 END), 0) as learn_btn3,
            COALESCE(SUM(CASE WHEN revlog.type IN (0, 2) AND revlog.ease = 4 THEN 1 ELSE 0 END), 0) as learn_btn4,
            
            COALESCE(SUM(CASE WHEN revlog.type = 1 AND revlog.lastIvl < 21 AND revlog.ease = 1 THEN 1 ELSE 0 END), 0) as young_btn1,
            COALESCE(SUM(CASE WHEN revlog.type = 1 AND revlog.lastIvl < 21 AND revlog.ease = 2 THEN 1 ELSE 0 END), 0) as young_btn2,
            COALESCE(SUM(CASE WHEN revlog.type = 1 AND revlog.lastIvl < 21 AND revlog.ease = 3 THEN 1 ELSE 0 END), 0) as young_btn3,
            COALESCE(SUM(CASE WHEN revlog.type = 1 AND revlog.lastIvl < 21 AND revlog.ease = 4 THEN 1 ELSE 0 END), 0) as young_btn4,
            
            COALESCE(SUM(CASE WHEN revlog.type = 1 AND revlog.lastIvl >= 21 AND revlog.ease = 1 THEN 1 ELSE 0 END), 0) as mature_btn1,
            COALESCE(SUM(CASE WHEN revlog.type = 1 AND revlog.lastIvl >= 21 AND revlog.ease = 2 THEN 1 ELSE 0 END), 0) as mature_btn2,
            COALESCE(SUM(CASE WHEN revlog.type = 1 AND revlog.lastIvl >= 21 AND revlog.ease = 3 THEN 1 ELSE 0 END), 0) as mature_btn3,
            COALESCE(SUM(CASE WHEN revlog.type = 1 AND revlog.lastIvl >= 21 AND revlog.ease = 4 THEN 1 ELSE 0 END), 0) as mature_btn4
        FROM revlog
        LEFT JOIN cards ON revlog.cid = cards.id
        WHERE revlog.type < {REVLOG_RESCHED}
        AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) >= {rev_start_ms} 
        AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) < {end_ms}
        {delta_filter} {part}
        GROUP BY hdid, bin_idx
    """
    rows_rev = _sliced_all(query_rev, slices, 2)

    # In delta mode only fetch counts for decks with new reviews: the merge keeps existing counts for the others.
    rows_counts = []
    if is_delta and min_rev_id is not None:
        query_counts = f"""
            SELECT
                COALESCE((CASE WHEN odid > 0 THEN odid ELSE did END), -1) as hdid,
                CASE
                    WHEN queue = -1 THEN 'suspended'
                    WHEN queue < -1 THEN 'buried'
                    WHEN type = 0 THEN 'new'
                    WHEN type = 1 THEN 'learn'
                    WHEN type = 3 THEN 'relearn'
                    WHEN type = 2 AND ivl < 21 THEN 'young'
                    WHEN type = 2 AND ivl >= 21 THEN 'mature'
                    ELSE 'other'
                END as status,
                COUNT(id)
            FROM cards
            WHERE (CASE WHEN odid > 0 THEN odid ELSE did END) IN (
                SELECT DISTINCT COALESCE((CASE WHEN c2.odid > 0 THEN c2.odid ELSE c2.did END), -1)
                FROM revlog rl LEFT JOIN cards c2 ON rl.cid = c2.id
                WHERE rl.id > {min_rev_id}
            )
            GROUP BY hdid, status
        """
    else:
        query_counts = """
            SELECT
                COALESCE((CASE WHEN odid > 0 THEN odid ELSE did END), -1) as hdid,
                CASE
                    WHEN queue = -1 THEN 'suspended'
                    WHEN queue < -1 THEN 'buried'
                    WHEN type = 0 THEN 'new'
                    WHEN type = 1 THEN 'learn'
                    WHEN type = 3 THEN 'relearn'
                    WHEN type = 2 AND ivl < 21 THEN 'young'
                    WHEN type = 2 AND ivl >= 21 THEN 'mature'
                    ELSE 'other'
                END as status,
                COUNT(id)
            FROM cards
            GROUP BY hdid, status
        """
    rows_counts = mw.col.db.all(query_counts)

    rows_future = []
    if is_delta and min_rev_id is not None:
        query_future = f"""
            SELECT COALESCE((CASE WHEN odid > 0 THEN odid ELSE did END), -1) as hdid, due, COUNT(*)
            FROM cards
            WHERE queue IN (2, 3)
            AND (CASE WHEN odid > 0 THEN odid ELSE did END) IN (
                SELECT DISTINCT COALESCE((CASE WHEN c2.odid > 0 THEN c2.odid ELSE c2.did END), -1)
                FROM revlog rl LEFT JOIN cards c2 ON rl.cid = c2.id
                WHERE rl.id > {min_rev_id}
            )
            GROUP BY hdid, due
        """
    else:
        query_future = """
            SELECT COALESCE((CASE WHEN odid > 0 THEN odid ELSE did END), -1) as hdid, due, COUNT(*)
            FROM cards
            WHERE queue IN (2, 3)
            GROUP BY hdid, due
        """
    rows_future = mw.col.db.all(query_future)

    # In delta mode, deleted card count doesn't change during reviews, reuse cached value.
    if is_delta and hasattr(provider_cls, "_session_deleted_count"):
        deleted_cards_count = provider_cls._session_deleted_count
    elif deleted_cards_count is None:
        deleted_cards_count = _deleted_cards_count(slices)

    # Hourly breakdown, also grouped by day to allow slicing
    rows_hourly = []
    def query_hourly(part):
        return f"""
        SELECT 
            COALESCE((CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END), -1) as hdid,
            {get_daystart_epoch_sql('CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END', is_ms=True)} as bin_idx,
            CAST(strftime('%H', (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) / 1000, 'unixepoch', 'localtime') AS INT) as hour_idx,
            COUNT(*) as total,
            SUM(CASE WHEN revlog.ease > 1 THEN 1 ELSE 0 END) as correct
        FROM revlog
        LEFT JOIN cards ON revlog.cid = cards.id
        WHERE revlog.type < {REVLOG_RESCHED}
        AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) >= {rev_start_ms}
        AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) < {end_ms}
        {delta_filter} {part}
        GROUP BY hdid, bin_idx, hour_idx
    """
    rows_hourly = _sliced_all(query_hourly, slices, 3)

    # Skipped in delta mode: a few reviews barely change the distributions and the full warmup updates them.
    rows_intervals = []
    if not is_delta:
        query_intervals = """
            SELECT COALESCE((CASE WHEN odid > 0 THEN odid ELSE did END), -1) as hdid, ivl, COUNT(*)
            FROM cards
            WHERE queue IN (2, 3) AND ivl > 0
            GROUP BY hdid, ivl
        """
        rows_intervals = mw.col.db.all(query_intervals)

    # Skipped in delta mode: the delta merge always drops fsrs from the cache, so computing it here would waste 100-300ms per review return.
    rows_fsrs = []
    if not is_delta:
        query_fsrs = """
            SELECT COALESCE((CASE WHEN odid > 0 THEN odid ELSE did END), -1) as hdid, data, due, ivl, queue
            FROM cards
            WHERE queue IN (1, 2, 3)
        """
        rows_fsrs = mw.col.db.all(query_fsrs)

    query_added = f"""
        SELECT COALESCE((CASE WHEN odid > 0 THEN odid ELSE did END), -1) as hdid, {get_daystart_epoch_sql('id', is_ms=True)} as bin_idx, COUNT(*) as count
        FROM cards
        WHERE id >= {card_start_ms} AND id < {end_ms}
        {delta_filter_added}
        GROUP BY hdid, bin_idx
    """
    rows_added = mw.col.db.all(query_added)

    # Deleted cards are gone from cards, but their id (the creation time) is still
    # in the revlog if they were reviewed. Count them as added in the virtual
    # Deleted entry (-1), so the Deleted tab has an Added chart and Total does not
    # lose cards on deletion. Never-reviewed deleted cards leave no trace.
    deleted_start_ms = 0 if (range_type == Period.TOTAL and not is_delta) else card_start_ms
    delta_filter_deleted_added = f"AND revlog.cid > {min_card_id}" if min_card_id is not None else ""
    query_added_deleted = f"""
        SELECT -1 as hdid, {get_daystart_epoch_sql('revlog.cid', is_ms=True)} as bin_idx, COUNT(DISTINCT revlog.cid) as count
        FROM revlog
        LEFT JOIN cards ON revlog.cid = cards.id
        WHERE cards.id IS NULL
        AND revlog.cid >= {deleted_start_ms} AND revlog.cid < {end_ms}
        {delta_filter_deleted_added}
        GROUP BY bin_idx
    """
    try:
        rows_added_deleted = mw.col.db.all(query_added_deleted)
    except Exception:
        rows_added_deleted = []
    rows_added = list(rows_added) + list(rows_added_deleted)

    rows_dist = []
    def query_dist(part):
        return f"""
        SELECT 
            COALESCE((CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END), -1) as hdid,
            CASE 
                WHEN revlog.type IN (0, 2) THEN 'learning'
                WHEN revlog.type = 1 AND revlog.lastIvl < 21 THEN 'young'
                WHEN revlog.type = 1 AND revlog.lastIvl >= 21 THEN 'mature'
                ELSE 'other'
            END as card_type,
            revlog.ease,
            COUNT(*) as count
        FROM revlog
        LEFT JOIN cards ON revlog.cid = cards.id
        WHERE revlog.type < {REVLOG_RESCHED}
        AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) >= {rev_start_ms} 
        AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) < {end_ms}
        {delta_filter} {part}
        GROUP BY (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END), card_type, revlog.ease
    """
    rows_dist = _sliced_all(query_dist, slices, 3)

    deck_data = {} # {did: {reviews: [], counts: {}, ...}}
    active_days_map = {} # {did: set(bin_idx)}

    def get_entry(did):
        if did not in deck_data:
            deck_data[did] = {
                "reviews": {}, # {bin_idx: data}
                "added": {},   # {bin_idx: count}
                "counts": {"new":0, "learn":0, "relearn":0, "young":0, "mature":0, "buried":0, "suspended":0, "deleted":0},
                "future": {},  # {due: count}
                "distribution": {
                    "learning": [0,0,0,0], "young": [0,0,0,0], "mature": [0,0,0,0]
                },
                "hourly": {h: {"total": 0, "correct": 0} for h in range(24)},
                "review_intervals": {"distribution": {}, "total": 0},
                "fsrs": {"stability": {}, "difficulty": {}, "retrievability": {}},
                "stats": {
                    "total_reviews": 0, "total_time_ms": 0, "total_passed": 0,
                    "rev_young": 0, "pass_young": 0, "rev_mat": 0, "pass_mat": 0,
                    "learn_count": 0, "relearn_count": 0, "young_count": 0, "mature_count": 0, "cram_count": 0,
                    "again": 0, "hard": 0, "good": 0, "easy": 0
                }
            }
        return deck_data[did]

    for did, bin_idx, reviews, t_ms, passed, r_young, p_young, r_mat, p_mat, l_c, rl_c, y_c, m_c, c_c, lt_ms, rlt_ms, yt_ms, mt_ms, ct_ms, c_ag, c_ha, c_go, c_ea, \
        l_b1, l_b2, l_b3, l_b4, y_b1, y_b2, y_b3, y_b4, m_b1, m_b2, m_b3, m_b4 in rows_rev:
        entry = get_entry(did)
        entry["reviews"][bin_idx] = {
            "reviews": reviews, "time_ms": t_ms, "passed": passed,
            "rev_young": r_young, "pass_young": p_young, "rev_mat": r_mat, "pass_mat": p_mat,
            "learn_count": l_c, "relearn_count": rl_c, "young_count": y_c, "mature_count": m_c, "cram_count": c_c,
            "learn_time_ms": lt_ms, "relearn_time_ms": rlt_ms, "young_time_ms": yt_ms, "mature_time_ms": mt_ms, "cram_time_ms": ct_ms,
            "again": c_ag, "hard": c_ha, "good": c_go, "easy": c_ea,
            "learn_btn1": l_b1, "learn_btn2": l_b2, "learn_btn3": l_b3, "learn_btn4": l_b4,
            "young_btn1": y_b1, "young_btn2": y_b2, "young_btn3": y_b3, "young_btn4": y_b4,
            "mature_btn1": m_b1, "mature_btn2": m_b2, "mature_btn3": m_b3, "mature_btn4": m_b4
        }
        s = entry["stats"]
        s["total_reviews"] += reviews
        s["total_time_ms"] += t_ms
        s["total_passed"] += passed
        s["rev_young"] += r_young
        s["pass_young"] += p_young
        s["rev_mat"] += r_mat
        s["pass_mat"] += p_mat
        s["learn_count"] += l_c
        s["relearn_count"] += rl_c
        s["young_count"] += y_c
        s["mature_count"] += m_c
        s["cram_count"] += c_c
        s["again"] += c_ag
        s["hard"] += c_ha
        s["good"] += c_go
        s["easy"] += c_ea

        if reviews > 0:
            active_days_map.setdefault(did, set()).add(bin_idx)

    for did, data in deck_data.items():
        s = data["stats"]
        tr = s["total_reviews"]
        if tr > 0:
            s["retention"] = (s["total_passed"] / tr * 100)
            s["active_days"] = len(active_days_map.get(did, set()))
            r1 = s["rev_young"]
            s["ret_young"] = (s["pass_young"] / r1 * 100) if r1 > 0 else 0
            rm = s["rev_mat"]
            s["ret_mat"] = (s["pass_mat"] / rm * 100) if rm > 0 else 0

    for did, status, count in rows_counts:
        e = get_entry(did)
        if status in e["counts"]:
            e["counts"][status] += count

    for did, due, count in rows_future:
        get_entry(did)["future"][due] = count

    for did, bin_idx, count in rows_added:
        get_entry(did)["added"][bin_idx] = count

    for did, ctype, ease, count in rows_dist:
        if ctype in ["learning", "young", "mature"] and 1 <= ease <= 4:
            get_entry(did)["distribution"][ctype][ease-1] = count

    for did, bin_idx, hour_idx, total, correct in rows_hourly:
        e = get_entry(did)
        if hour_idx in e["hourly"]:
            ih = e["hourly"][hour_idx]
            ih["total"] += total
            ih["correct"] += correct

        if bin_idx in e["reviews"]:
            day_hz = e["reviews"][bin_idx].setdefault("hourly", {h: {"total": 0, "correct": 0} for h in range(24)})
            day_hz[hour_idx]["total"] += total
            day_hz[hour_idx]["correct"] += correct

    for did, ivl, count in rows_intervals:
        e = get_entry(did)
        dist = e["review_intervals"]["distribution"]
        dist[ivl] = dist.get(ivl, 0) + count
        e["review_intervals"]["total"] += count

    has_pb = False
    try:
        from anki.cards_pb2 import CardData
        has_pb = True
    except ImportError:
        pass
    import json
    from ...fsrs_math import retrievability
    today_sched = mw.col.sched.today

    for did, data, due, ivl, queue in rows_fsrs:
        if not data: continue
        entry = get_entry(did)
        fsrs = entry["fsrs"]

        s = 0.0; d = 0.0; decay = None
        if isinstance(data, bytes) and has_pb:
            try:
                cd = CardData.FromString(data)
                if cd.HasField("fsrs"):
                    s = cd.fsrs.stability
                    d = cd.fsrs.difficulty
            except Exception: log_swallowed()
        elif isinstance(data, str):
            try:
                jd = json.loads(data)
                if "s" in jd and "d" in jd:
                    s = float(jd["s"]); d = float(jd["d"]); decay = jd.get("decay")
                elif "cd" in jd:
                    cd = jd["cd"]
                    if isinstance(cd, str): cd = json.loads(cd)
                    if "s" in cd and "d" in cd:
                        s = float(cd["s"]); d = float(cd["d"])
            except Exception: log_swallowed()

        # Same buckets as the FSRS refresh (population._populate_fsrs_cache), so the
        # charts do not change when that refresh replaces this first pass.
        if s or d:
            s_int = min(int(s), 100)
            fsrs["stability"][s_int] = fsrs["stability"].get(s_int, 0) + 1

            diff_pct = int(((d - 1) / 9.0) * 100) if d > 0 else 0
            diff_pct = max(0, min(100, diff_pct))
            fsrs["difficulty"][diff_pct] = fsrs["difficulty"].get(diff_pct, 0) + 1

            if queue == 2 and s > 0:
                elapsed = max(0, today_sched - (due - ivl))
                r_pct = max(0, min(100, int(retrievability(elapsed, s, decay) * 100)))
                fsrs["retrievability"][r_pct] = fsrs["retrievability"].get(r_pct, 0) + 1

    get_entry(-1)["counts"]["deleted"] = deleted_cards_count

    from datetime import datetime as _dt

    from ...data.core.streaks import current_streak_from_dates

    for did, data in deck_data.items():
        data["counts"]["total"] = sum(data["counts"][k] for k in ["new", "learn", "relearn", "young", "mature", "suspended", "buried", "deleted"])

        # Day keys are the instant of local midnight of each logical day: counted as dates,
        # so the streak follows the same "today or yesterday" rule as everywhere else.
        reviews_bins = data["reviews"]  # {bin_idx: data}
        dates = [
            _dt.fromtimestamp(b_idx / 1000).strftime("%Y-%m-%d")
            for b_idx, r in reviews_bins.items()
            if r.get("reviews", 0) > 0
        ]
        data["stats"]["streak"] = current_streak_from_dates(dates)

    return deck_data





