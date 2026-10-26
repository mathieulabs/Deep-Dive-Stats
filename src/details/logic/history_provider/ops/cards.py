# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..shared import Config, Period, datetime, get_rollover_offset_ms, get_time_range_ms, mw, timedelta
from ... import rollover_hour
from .....utils import get_logical_day_sql, logical_day_number
from ...logger import log_error
from ...logger import log_swallowed


def fetch_added_history(
    provider_cls,
    addon_config,
    deck_id=None,
    range_type=Period.YEAR,
    is_deleted=False,
    override_start_ms=None,
    override_end_ms=None,
    override_bin_ms=None,
    did_limit=None,
    custom_days=7,
    custom_type="relative",
    start_date_str="",
    end_date_str="",
):
    if is_deleted:
        did_limit = ""
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
            if is_deleted:
                first_card_ms = mw.col.db.scalar("SELECT MIN(cid) FROM revlog LEFT JOIN cards ON revlog.cid = cards.id WHERE cards.id IS NULL")
            else:
                first_card_ms = mw.col.db.scalar(f"SELECT MIN(id) FROM cards WHERE 1=1 {did_limit}")
            start_ms = first_card_ms or int((datetime.now() - timedelta(days=365)).timestamp() * 1000)

    offset_ms = get_rollover_offset_ms()
    if override_bin_ms is not None:
        ms_per_bin = override_bin_ms
        is_hourly = ms_per_bin < 86400000
    else:
        is_hourly = range_type in [Period.TODAY, Period.YESTERDAY] or (end_ms - start_ms <= 2 * 86400 * 1000)
        ms_per_bin = 600000 if is_hourly else 86400000

    def bin_sql(column):
        # Days are Anki days in local time (a day with a clock change lasts 23 or 25 hours).
        if is_hourly:
            return f"CAST((({column} - {offset_ms}) / {ms_per_bin}) AS INT)"
        return get_logical_day_sql(column)

    if is_deleted:
        query = f"""
            SELECT
                {bin_sql("cid")} as bin_idx,
                COUNT(DISTINCT cid) as count
            FROM revlog
            LEFT JOIN cards ON revlog.cid = cards.id
            WHERE cid >= {start_ms} AND cid < {end_ms}
            AND cards.id IS NULL
            GROUP BY bin_idx
            ORDER BY bin_idx DESC
        """
        initial_count_query = f"""
            SELECT COUNT(DISTINCT cid)
            FROM revlog
            LEFT JOIN cards ON revlog.cid = cards.id
            WHERE cid < {start_ms}
            AND cards.id IS NULL
        """
    else:
        query = f"""
            SELECT
                {bin_sql("id")} as bin_idx,
                COUNT(*) as count
            FROM cards
            WHERE id >= {start_ms} AND id < {end_ms}
            {did_limit}
            GROUP BY bin_idx
            ORDER BY bin_idx DESC
        """
        initial_count_query = f"SELECT COUNT(*) FROM cards WHERE id < {start_ms} {did_limit}"

    rows = mw.col.db.all(query)
    row_map = {r[0]: r[1] for r in rows}

    initial_count = mw.col.db.scalar(initial_count_query) or 0
    total_in_range = sum(row_map.values())

    history = []
    months_en = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    if is_hourly:
        end_idx = int((end_ms - 1 - offset_ms) / ms_per_bin)
        start_idx = int((start_ms - offset_ms) / ms_per_bin)
    else:
        end_idx = logical_day_number(end_ms - 1)
        start_idx = logical_day_number(start_ms)

    use_asc = override_start_ms is not None
    bin_range = range(start_idx, end_idx + 1) if use_asc else range(end_idx, start_idx - 1, -1)

    current_cum = initial_count
    if not use_asc:
        current_cum = initial_count + total_in_range

    for b_idx in bin_range:
        count = row_map.get(b_idx, 0)

        if is_hourly:
            dt = datetime.fromtimestamp(((b_idx * ms_per_bin) + offset_ms) / 1000)
            date_str = dt.strftime("%Y-%m-%d %H:%M")
            pretty_date = f"{months_en[dt.month-1]} {dt.day:02d}, {dt.strftime('%H:%M')}"
        else:
            day = datetime(1970, 1, 1) + timedelta(days=b_idx)
            date_str = day.strftime("%Y-%m-%d")
            pretty_date = f"{months_en[day.month-1]} {day.day:02d}, {day.year}"

        history.append(
            {
                "date": date_str,
                "pretty_date": pretty_date,
                "count": count,
                "cumulative": current_cum,
            }
        )

        if use_asc:
            current_cum += count
        else:
            current_cum -= count

    return history


def fetch_card_counts(provider_cls, addon_config, deck_id=None, is_deleted=False, did_limit=None):

    if is_deleted:
        deleted_count = (
            mw.col.db.scalar(
                """
                SELECT COUNT(DISTINCT cid)
                FROM revlog
                WHERE cid NOT IN (SELECT id FROM cards)
                """
            )
            or 0
        )
        counts = {
            "new": 0,
            "learn": 0,
            "relearn": 0,
            "young": 0,
            "mature": 0,
            "suspended": 0,
            "buried": 0,
            "deleted": deleted_count,
            "total": deleted_count,
        }
        try:
            from ..deleted_states import deleted_card_states

            info = deleted_card_states()
            if info:
                counts.update(info["counts"])
        except Exception:
            log_swallowed()
        return counts

    if did_limit is None:
        did_limit = provider_cls._get_did_limit(addon_config, deck_id)

    query = f"""
        SELECT
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
            COUNT(*)
        FROM cards
        WHERE 1=1 {did_limit}
        GROUP BY status
    """

    rows = mw.col.db.all(query)
    counts = {"new": 0, "learn": 0, "relearn": 0, "young": 0, "mature": 0, "suspended": 0, "buried": 0}
    for status, count in rows:
        if status in counts:
            counts[status] = count

    if not hasattr(provider_cls, "_session_deleted_count"):
        provider_cls._session_deleted_count = (
            mw.col.db.scalar(
                """
                SELECT COUNT(DISTINCT revlog.cid)
                FROM revlog
                LEFT JOIN cards ON revlog.cid = cards.id
                WHERE cards.id IS NULL
                """
            )
            or 0
        )

    counts["deleted"] = provider_cls._session_deleted_count
    counts["total"] = sum(counts.values())
    return counts


def fetch_future_reviews(provider_cls, deck_id, target_year, cfg, did_limit=None):
    heatmap_data = {}
    try:
        if did_limit is None:
            did_limit = provider_cls._get_did_limit(cfg, deck_id)

        today_sched = mw.col.sched.today
        year_start_date = datetime(target_year, 1, 1).date()
        year_end_date = datetime(target_year, 12, 31).date()

        now_date = datetime.now().date()
        if datetime.now().hour < rollover_hour():
            now_date -= timedelta(days=1)

        days_until_year_start = (year_start_date - now_date).days
        days_until_year_end = (year_end_date - now_date).days

        start_due = today_sched + max(0, days_until_year_start)
        end_due = today_sched + days_until_year_end

        if start_due <= end_due:
            query = f"""
                SELECT due, count()
                FROM cards
                WHERE queue IN (1, 2, 3)
                AND (due >= {start_due} OR due > 1000000000)
                AND (due <= {end_due} OR due > 1000000000)
                {did_limit}
                GROUP BY due
            """
            try:
                rows = mw.col.db.all(query)
                from ...logger import log_debug

                log_debug(
                    f"[PROVIDER] fetch_future_reviews SQL returned {len(rows)} rows for deck={deck_id}, range={target_year}",
                    tag="PROVIDER",
                )
            except Exception as e:
                from ...logger import log_debug

                log_debug(f"Error fetching future reviews SQL: {e}", tag="PROVIDER")
                rows = []

            for due, count in rows:
                if due > 1000000000:
                    target_date = now_date
                else:
                    days_ahead = due - today_sched
                    target_date = now_date + timedelta(days=days_ahead)

                date_str = target_date.strftime("%Y-%m-%d")
                heatmap_data[date_str] = heatmap_data.get(date_str, 0) + count

    except Exception as e:
        log_error(f"Error fetching future reviews: {e}")
    return heatmap_data

