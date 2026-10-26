# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .....utils import excluded_days_clause, excluded_days_need_cards
from ..shared import (
    Config,
    REVLOG_RESCHED,
    Period,
    datetime,
    get_daystart_epoch_sql,
    get_rollover_offset_ms,
    get_time_range_ms,
    mw,
    timedelta,
)
from ... import rollover_hour
from ...data.core.empty_deck import did_limit_has_no_cards


def fetch_history(
    provider_cls,
    addon_config,
    deck_id=None,
    range_type=Period.YEAR,
    is_deleted=False,
    override_start_ms=None,
    override_end_ms=None,
    override_bin_ms=None,
    minimal=False,
    did_limit=None,
    custom_days=7,
    custom_type="relative",
    start_date_str="",
    end_date_str="",
    align_with_added=False,
):
    """Fetch metrics for a specific range with appropriate granularity."""
    from ...logger import log_debug

    if is_deleted:
        did_limit = "AND (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END) IS NULL"
    elif did_limit is None:
        did_limit = provider_cls._get_did_limit(addon_config, deck_id)

    if override_start_ms is not None and override_end_ms is not None:
        start_ms = override_start_ms
        end_ms = override_end_ms
    else:
        week_start = addon_config.config.get(Config.WEEK_START, 0)
        start_ms, end_ms, _, _ = get_time_range_ms(
            range_type,
            week_start=week_start,
            custom_days=custom_days,
            custom_type=custom_type,
            start_date_str=start_date_str,
            end_date_str=end_date_str,
        )

        if range_type == Period.TOTAL:
            first_rev_ms = 0
            if align_with_added:
                if did_limit and not is_deleted:
                    first_rev_ms = mw.col.db.scalar(f"SELECT MIN(id) FROM cards as cards WHERE 1=1 {did_limit}")
                if not first_rev_ms:
                    first_rev_ms = mw.col.db.scalar("SELECT MIN(id) FROM cards WHERE id > 0")

            if not first_rev_ms:
                first_rev_ms = mw.col.db.scalar(
                    f"""
                    SELECT MIN(revlog.id)
                    FROM revlog
                    LEFT JOIN cards ON revlog.cid = cards.id
                    WHERE revlog.id > 0 {did_limit} {excluded_days_clause()}
                    """
                )

            start_ms = first_rev_ms or int((datetime.now() - timedelta(days=365)).timestamp() * 1000)

    offset_ms = get_rollover_offset_ms()

    if override_bin_ms is not None:
        ms_per_bin = override_bin_ms
        is_hourly = ms_per_bin < 86400000
    else:
        is_hourly = range_type in [Period.TODAY, Period.YESTERDAY] or (end_ms - start_ms <= 2 * 86400 * 1000)
        ms_per_bin = 600000 if is_hourly else 86400000

    join_clause = "LEFT JOIN cards ON revlog.cid = cards.id" if (did_limit or excluded_days_need_cards()) else ""

    bin_expr = (
        f"CAST(((CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END - {offset_ms}) / {ms_per_bin}) AS INT)"
        if is_hourly
        else get_daystart_epoch_sql("CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END", is_ms=True)
    )

    if minimal:
        query = f"""
            SELECT
                {bin_expr} as bin_idx,
                COUNT(*) as reviews,
                SUM(revlog.time) as time_ms,
                SUM(CASE WHEN revlog.ease > 1 THEN 1 ELSE 0 END) as passed
            FROM revlog
            {join_clause}
            WHERE revlog.type < {REVLOG_RESCHED}
            AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) >= {start_ms}
            AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) < {end_ms}
            {did_limit} {excluded_days_clause()}
            GROUP BY bin_idx
            ORDER BY bin_idx DESC
        """
    else:
        query = f"""
            SELECT
                {bin_expr} as bin_idx,
                COUNT(*) as reviews,
                SUM(revlog.time) as time_ms,
                SUM(CASE WHEN revlog.ease > 1 THEN 1 ELSE 0 END) as passed,
                SUM(CASE WHEN revlog.ease > 0 AND NOT (revlog.type = 3 AND revlog.factor = 0) AND (revlog.type = 1 OR revlog.lastIvl <= -86400 OR revlog.lastIvl >= 1) AND revlog.lastIvl < 21 THEN 1 ELSE 0 END) as rev_young,
                SUM(CASE WHEN revlog.ease > 0 AND NOT (revlog.type = 3 AND revlog.factor = 0) AND (revlog.type = 1 OR revlog.lastIvl <= -86400 OR revlog.lastIvl >= 1) AND revlog.lastIvl < 21 AND revlog.ease > 1 THEN 1 ELSE 0 END) as pass_young,
                SUM(CASE WHEN revlog.ease > 0 AND NOT (revlog.type = 3 AND revlog.factor = 0) AND (revlog.type = 1 OR revlog.lastIvl <= -86400 OR revlog.lastIvl >= 1) AND revlog.lastIvl >= 21 THEN 1 ELSE 0 END) as rev_mat,
                SUM(CASE WHEN revlog.ease > 0 AND NOT (revlog.type = 3 AND revlog.factor = 0) AND (revlog.type = 1 OR revlog.lastIvl <= -86400 OR revlog.lastIvl >= 1) AND revlog.lastIvl >= 21 AND revlog.ease > 1 THEN 1 ELSE 0 END) as pass_mat,
                SUM(CASE WHEN revlog.type = 0 THEN 1 ELSE 0 END) as learn_count,
                SUM(CASE WHEN revlog.type = 2 THEN 1 ELSE 0 END) as relearn_count,
                SUM(CASE WHEN revlog.type = 1 AND revlog.lastIvl < 21 THEN 1 ELSE 0 END) as young_count,
                SUM(CASE WHEN revlog.type = 1 AND revlog.lastIvl >= 21 THEN 1 ELSE 0 END) as mature_count,
                SUM(CASE WHEN revlog.type = 3 THEN 1 ELSE 0 END) as cram_count,
                SUM(CASE WHEN revlog.type = 0 THEN revlog.time ELSE 0 END) as learn_time_ms,
                SUM(CASE WHEN revlog.type = 2 THEN revlog.time ELSE 0 END) as relearn_time_ms,
                SUM(CASE WHEN revlog.type = 1 AND revlog.lastIvl < 21 THEN revlog.time ELSE 0 END) as young_time_ms,
                SUM(CASE WHEN revlog.type = 1 AND revlog.lastIvl >= 21 THEN revlog.time ELSE 0 END) as mature_time_ms,
                SUM(CASE WHEN revlog.type = 3 THEN revlog.time ELSE 0 END) as cram_time_ms,
                SUM(CASE WHEN revlog.type IN (0, 2) AND revlog.ease = 1 THEN 1 ELSE 0 END) as learn_btn1,
                SUM(CASE WHEN revlog.type IN (0, 2) AND revlog.ease = 2 THEN 1 ELSE 0 END) as learn_btn2,
                SUM(CASE WHEN revlog.type IN (0, 2) AND revlog.ease = 3 THEN 1 ELSE 0 END) as learn_btn3,
                SUM(CASE WHEN revlog.type IN (0, 2) AND revlog.ease = 4 THEN 1 ELSE 0 END) as learn_btn4,
                SUM(CASE WHEN revlog.type = 1 AND revlog.lastIvl < 21 AND revlog.ease = 1 THEN 1 ELSE 0 END) as young_btn1,
                SUM(CASE WHEN revlog.type = 1 AND revlog.lastIvl < 21 AND revlog.ease = 2 THEN 1 ELSE 0 END) as young_btn2,
                SUM(CASE WHEN revlog.type = 1 AND revlog.lastIvl < 21 AND revlog.ease = 3 THEN 1 ELSE 0 END) as young_btn3,
                SUM(CASE WHEN revlog.type = 1 AND revlog.lastIvl < 21 AND revlog.ease = 4 THEN 1 ELSE 0 END) as young_btn4,
                SUM(CASE WHEN revlog.type = 1 AND revlog.lastIvl >= 21 AND revlog.ease = 1 THEN 1 ELSE 0 END) as mature_btn1,
                SUM(CASE WHEN revlog.type = 1 AND revlog.lastIvl >= 21 AND revlog.ease = 2 THEN 1 ELSE 0 END) as mature_btn2,
                SUM(CASE WHEN revlog.type = 1 AND revlog.lastIvl >= 21 AND revlog.ease = 3 THEN 1 ELSE 0 END) as mature_btn3,
                SUM(CASE WHEN revlog.type = 1 AND revlog.lastIvl >= 21 AND revlog.ease = 4 THEN 1 ELSE 0 END) as mature_btn4
            FROM revlog
            {join_clause}
            WHERE revlog.type < {REVLOG_RESCHED}
            AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) >= {start_ms}
            AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) < {end_ms}
            {did_limit} {excluded_days_clause()}
            GROUP BY bin_idx
            ORDER BY bin_idx DESC
        """

    try:
        rows = [] if did_limit_has_no_cards(did_limit) else mw.col.db.all(query)
        log_debug(
            f"[PROVIDER] fetch_history SQL returned {len(rows)} rows for deck={deck_id}, range={range_type}. did_limit={did_limit}",
            tag="PROVIDER",
        )
    except Exception as e:
        log_debug(f"[PROVIDER] fetch_history SQL EXCEPTION: {e}", tag="PROVIDER")
        rows = []

    row_map = {r[0]: r[1:] for r in rows}

    history = []
    offset_hour = rollover_hour()
    offset_ms_calc = get_rollover_offset_ms()
    months_en = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    use_asc = override_start_ms is not None

    if is_hourly:
        end_idx = int((end_ms - 1 - offset_ms) / ms_per_bin)
        start_idx = int((start_ms - offset_ms) / ms_per_bin)
        bin_range = range(start_idx, end_idx + 1) if use_asc else range(end_idx, start_idx - 1, -1)
    else:
        start_logical = (datetime.fromtimestamp(start_ms / 1000) - timedelta(hours=offset_hour)).date()
        end_logical = (datetime.fromtimestamp((end_ms - 1) / 1000) - timedelta(hours=offset_hour)).date()

        bin_range = []
        curr_d = start_logical
        while curr_d <= end_logical:
            dt_start = datetime(curr_d.year, curr_d.month, curr_d.day, 0, 0, 0)
            bin_range.append(int(dt_start.timestamp() * 1000))
            curr_d += timedelta(days=1)

        if not use_asc:
            bin_range.reverse()

    for b_idx in bin_range:
        if is_hourly:
            ms = (b_idx * ms_per_bin) + offset_ms_calc
            dt = datetime.fromtimestamp(ms / 1000)
            date_str = dt.strftime("%Y-%m-%d %H:%M")
            pretty_date = f"{months_en[dt.month-1]} {dt.day:02d}, {dt.strftime('%H:%M')}"
            logical_dt = dt - timedelta(hours=offset_hour)
            logical_date = logical_dt.strftime("%Y-%m-%d")
        else:
            logical_date = datetime.fromtimestamp(b_idx / 1000).strftime("%Y-%m-%d")
            date_str = logical_date
            logical_dt = datetime.strptime(logical_date, "%Y-%m-%d")
            pretty_date = f"{months_en[logical_dt.month-1]} {logical_dt.day:02d}, {logical_dt.year}"

        row = row_map.get(b_idx)

        if minimal:
            if row is None:
                history.append(
                    {
                        "date": date_str,
                        "pretty_date": pretty_date,
                        "logical_date": logical_date,
                        "reviews": 0,
                        "time_ms": 0,
                        "passed": 0,
                        "retention": None,
                    }
                )
            else:
                history.append(
                    {
                        "date": date_str,
                        "pretty_date": pretty_date,
                        "logical_date": logical_date,
                        "reviews": row[0] or 0,
                        "time_ms": row[1] or 0,
                        "passed": row[2] or 0,
                        "retention": (row[2] / row[0] * 100) if row[0] and row[0] > 0 else None,
                    }
                )
        else:
            if row is None:
                history.append(
                    {
                        "date": date_str,
                        "pretty_date": pretty_date,
                        "logical_date": logical_date,
                        "reviews": 0,
                        "time_ms": 0,
                        "passed": 0,
                        "retention": None,
                        "rev_young": 0,
                        "pass_young": 0,
                        "ret_young": None,
                        "rev_mat": 0,
                        "pass_mat": 0,
                        "ret_mat": None,
                        "learn_count": 0,
                        "relearn_count": 0,
                        "young_count": 0,
                        "mature_count": 0,
                        "cram_count": 0,
                        "learn_time_ms": 0,
                        "relearn_time_ms": 0,
                        "young_time_ms": 0,
                        "mature_time_ms": 0,
                        "cram_time_ms": 0,
                        "learning_buttons": [0, 0, 0, 0],
                        "young_buttons": [0, 0, 0, 0],
                        "mature_buttons": [0, 0, 0, 0],
                    }
                )
            else:
                history.append(
                    {
                        "date": date_str,
                        "pretty_date": pretty_date,
                        "logical_date": logical_date,
                        "reviews": row[0] or 0,
                        "time_ms": row[1] or 0,
                        "passed": row[2] or 0,
                        "retention": (row[2] / row[0] * 100) if row[0] and row[0] > 0 else None,
                        "rev_young": row[3] or 0,
                        "pass_young": row[4] or 0,
                        "ret_young": (row[4] / row[3] * 100) if row[3] and row[3] > 0 else None,
                        "rev_mat": row[5] or 0,
                        "pass_mat": row[6] or 0,
                        "ret_mat": (row[6] / row[5] * 100) if row[5] and row[5] > 0 else None,
                        "learn_count": row[7] or 0,
                        "relearn_count": row[8] or 0,
                        "young_count": row[9] or 0,
                        "mature_count": row[10] or 0,
                        "cram_count": row[11] or 0,
                        "learn_time_ms": row[12] or 0,
                        "relearn_time_ms": row[13] or 0,
                        "young_time_ms": row[14] or 0,
                        "mature_time_ms": row[15] or 0,
                        "cram_time_ms": row[16] or 0,
                        "learning_buttons": [row[17] or 0, row[18] or 0, row[19] or 0, row[20] or 0],
                        "young_buttons": [row[21] or 0, row[22] or 0, row[23] or 0, row[24] or 0],
                        "mature_buttons": [row[25] or 0, row[26] or 0, row[27] or 0, row[28] or 0],
                    }
                )

    return history

