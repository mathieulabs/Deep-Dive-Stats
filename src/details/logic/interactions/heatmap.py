# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ....utils import excluded_days_clause
from datetime import datetime
from aqt import mw
from .. import ConfigManager, rollover_hour
from ..logger import log_error
from ..logger import log_swallowed

class HeatmapInteractions:
    @staticmethod
    def open_browser_for_date(date_str, did=None):
        """Find cards reviewed on a specific date asynchronously and show them in the Browser."""
        from ..logger import log_debug
        log_debug(f"HeatmapInteractions.open_browser_for_date: date={date_str}, did={did}", tag="INTERACTION")
        mw.taskman.run_in_background(
            lambda: HeatmapInteractions._fetch_heatmap_cids_bg(date_str, did),
            on_done=HeatmapInteractions._on_cids_fetched
        )

    @staticmethod
    def _fetch_heatmap_cids_bg(date_str, did):
        """Background worker to fetch CIDs (past) or query (future) for a date."""
        try:
            from ..history_provider import HistoryProvider
            from ..logger import log_debug
            from datetime import timedelta

            dt = datetime.strptime(date_str, "%Y-%m-%d")
            rollover = rollover_hour()
            now = datetime.now()

            if now.hour < rollover:
                logical_today = (now - timedelta(days=1)).date()
            else:
                logical_today = now.date()

            is_future = dt.date() > logical_today

            deck_name = None
            if did is not None:
                if isinstance(did, str) and not did.isdigit():
                    deck_name = did
                else:
                    try:
                        deck_name = mw.col.decks.name(did)
                    except Exception:
                        log_swallowed()

            if is_future:
                days_ahead = (dt.date() - logical_today).days
                query = f"prop:due={days_ahead}"
                log_debug(f"HeatmapInteractions: Future date detected. Query='{query}'", tag="INTERACTION")
                return (None, deck_name, date_str, query)
            else:
                start_ms = int((dt.timestamp() + rollover * 3600) * 1000)
                end_ms = start_ms + (24 * 3600 * 1000)

                cfg = ConfigManager(mw)
                did_limit = HistoryProvider._get_did_limit(cfg, did)

                sql = f"""
                    SELECT DISTINCT cards.id 
                    FROM revlog 
                    JOIN cards ON revlog.cid = cards.id 
                    WHERE (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) >= {start_ms} 
                    AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) < {end_ms}
                    {did_limit} {excluded_days_clause()}
                """
                cids = mw.col.db.list(sql)
                log_debug(f"HeatmapInteractions: Past date. Found {len(cids)} cids", tag="INTERACTION")

                # Falling back to pending cards if Today and no reviews found
                if not cids and dt.date() == logical_today:
                    log_debug("HeatmapInteractions: No reviews today. Falling back to 'is:due'", tag="INTERACTION")
                    return (None, deck_name, date_str, "is:due")

                return (cids, deck_name, date_str, None)

        except Exception as e:
            import traceback
            log_error(f"Error fetching heatmap cids: {e}\n{traceback.format_exc()}")
            return ([], None, date_str, None)

    @staticmethod
    def _on_cids_fetched(future_or_result):
        """Callback on main thread to open browser with found CIDs or query."""
        try:
            if hasattr(future_or_result, "result"):
                res = future_or_result.result()
            else:
                res = future_or_result

            if len(res) == 4:
                card_ids, deck_name, date_str, direct_query = res
            else:
                card_ids, deck_name, date_str = res
                direct_query = None

        except Exception as e:
            log_error(f"Error retrieving heatmap cids: {e}")
            return

        search_parts = []
        if direct_query:
            search_parts.append(direct_query)
        elif card_ids:
            cid_str = ",".join(str(cid) for cid in card_ids)
            search_parts.append(f"cid:{cid_str}")
        else:
            from aqt.utils import tooltip
            tooltip(f"No cards found for {date_str}")
            return

        if deck_name:
            search_parts.append(f'deck:"{deck_name}"')

        from aqt import dialogs
        browser = dialogs.open("Browser", mw)
        browser.search_for_terms(" ".join(search_parts))



