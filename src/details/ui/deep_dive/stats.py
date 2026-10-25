# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from .. import Period, Config
from ...widgets.stats_cards import build_dashboard_history_totals, build_dashboard_stat_values, apply_dashboard_stat_values
from .stats_parts.runtime_updates import update_stats_from_history
from ...logic.logger import log_swallowed

DELETED_TAB_DID = "__deleted_cards__"

class DeepDiveStatsMixin:
    def _find_row_data(self, deck_identifier, title, period_range):
        if isinstance(deck_identifier, (list, tuple)):
            return self._merged_row_data(deck_identifier)
        current_idx = self.dialog.tab_widget.currentIndex()
        tab_stats = self.dialog.tab_stats.get(current_idx)
        if not tab_stats:
            return None
        results = tab_stats.get("results", [])

        row_data = None
        if self.dialog.view_mode == 'time':
            for r in results:
                if str(r.get("full_name")) == str(deck_identifier) or str(r.get("did")) == str(deck_identifier):
                    row_data = r
                    break
            if not row_data:
                for r in results:
                    if r.get("display_name") == deck_identifier:
                        row_data = r
                        break
            if not row_data and (deck_identifier in ["[[TOTAL]]", "0", 0] or title in ["Total", "Collection"] or title.upper() == "TOTAL"):
                row_data = next((r for r in results if r.get("is_total_row")), None)
        else:
            for r in results:
                if str(r.get("range_type")) == str(period_range) or r.get("title") == title:
                    row_data = r
                    break
            if not row_data and (title in ["Total", "Collection"] or title.upper() == "TOTAL" or deck_identifier in ["0", 0]):
                row_data = next((r for r in results if r.get("is_total_row")), None)

        if not row_data and (deck_identifier in ["[[TOTAL]]", "0", 0] or title == "Collection"):
            row_data = next((r for r in results if r.get("is_total_row")), None)
            if not row_data:
                row_data = {"is_total_row": True, "did": None, "title": "Collection"}

        return row_data

    def _merged_row_data(self, deck_ids):
        """Row data for a multi-deck selection: the sum of the selected rows."""
        tab_stats = self.dialog.tab_stats.get(self.dialog.tab_widget.currentIndex())
        results = (tab_stats or {}).get("results", [])
        wanted = {str(d) for d in deck_ids}
        rows = [r for r in results if (r.get("is_deleted") and "deleted" in deck_ids) or (not r.get("is_deleted") and str(r.get("did")) in wanted)]
        if not rows:
            return None
        merged = {"did": list(deck_ids), "is_deleted": False, "full_name": ", ".join(str(r.get("full_name", "")) for r in rows),
                  "title": f"{len(rows)} decks", "is_multi": True}
        for r in rows:
            for k, v in r.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool) and k != "did":
                    merged[k] = merged.get(k, 0) + v
        return merged

    def _resolve_tab_config(self, current_idx, period_range):
        """Safely resolve tab configuration based on view mode and period range."""
        all_tabs_config = self.dialog.get_tabs_config()
        if self.dialog.view_mode == 'time':
             active_tabs = self.dialog.get_active_tabs_config()
             if 0 <= current_idx < len(active_tabs):
                  return active_tabs[current_idx]
             return next((t for t in all_tabs_config if t.get("enabled", True)), all_tabs_config[0])
        else:
             # Deck view mode: period_range is the target time span; find the matching tab config.
             tab_config = next((t for t in all_tabs_config if str(t.get("range")) == str(period_range)), None)
             if not tab_config:
                  tab_config = next((t for t in all_tabs_config if t.get("enabled", True)), all_tabs_config[0])
             return tab_config

    def _prepare_history_params(self, row_data, deck_identifier, period_range):
        """Capture all UI state needed for history fetch (MUST run on main thread)."""
        current_idx = self.dialog.tab_widget.currentIndex()
        tab_config = self._resolve_tab_config(current_idx, period_range)

        target_did = row_data.get("did")
        # Deck view special case:
        # - `deck_identifier == "collection"` => Collection tab
        # - `deck_identifier is None` or deleted sentinel => Deleted Cards tab
        is_deleted_tab = (
            self.dialog.view_mode == 'deck'
            and deck_identifier in (None, DELETED_TAB_DID)
        )
        if is_deleted_tab:
            target_did = -1
        if target_did is None and self.dialog.view_mode != 'time':
             target_did = tab_config.get("deck_id")

        if period_range is not None:
             history_range = int(period_range)
        else:
             history_range = tab_config.get("range", Period.TOTAL)

        is_deleted = row_data.get("is_deleted", False) or is_deleted_tab

        added_sync = self._get_dd_widget_setting("added", "sync_zoom", False)

        custom_days = tab_config.get("custom_days", 7)
        custom_type = tab_config.get("custom_type", "relative")
        start_date_str = tab_config.get("start_date", "")
        end_date_str = tab_config.get("end_date", "")

        return target_did, history_range, is_deleted, added_sync, custom_days, custom_type, start_date_str, end_date_str

    def _fetch_history_bg(self, target_did, history_range, is_deleted, added_sync=False, custom_days=7, custom_type="relative", start_date_str="", end_date_str=""):
        """Fetch history data and full context (safe to run on background thread - pure SQL)."""
        widget_settings = self.addon_config.config.get(Config.DEEP_DIVE_WIDGET_SETTINGS, {})

        if isinstance(target_did, list):
            from ...widgets.pinned.widget_factory.utils import PinnedDataManager

            ctx = PinnedDataManager.get_context(
                target_did, history_range, cfg=self.addon_config,
                custom_days=custom_days, custom_type=custom_type,
                start_date_str=start_date_str, end_date_str=end_date_str,
                allow_sync_check=False, allow_slow_ops=True,
            ) or {}
            return ctx.get("reviews", []), history_range, ctx

        from ...widgets.pinned.context_access import fetch_pinned_context_data

        ctx = fetch_pinned_context_data(
            target_did,
            history_range,
            cfg=self.addon_config,
            custom_days=custom_days, custom_type=custom_type,
            start_date_str=start_date_str, end_date_str=end_date_str,
            widget_settings=widget_settings
        )
        history_data = ctx.get("reviews", [])
        return history_data, history_range, ctx

    def _build_stats_section(self, row_data, target_layout=None, manual_add=False, deck_id=None, time_span=None):
        reviews = row_data.get("reviews", row_data.get("total_reviews", 0))
        time_ms = row_data.get("time_ms", row_data.get("total_time_ms", 0))
        time_hours = time_ms / (1000 * 3600)

        pass_young = row_data.get("pass_young", 0)
        rev_young = row_data.get("rev_young", 0)
        pass_mat = row_data.get("pass_mat", 0)
        rev_mat = row_data.get("rev_mat", 0)

        prec = self.dialog.addon_config.config.get(Config.STATS_PRECISION, 2)

        if not hasattr(self, 'time_card'):
            self.time_card = self.dialog.card_time
            self.rev_card = self.dialog.card_reviews
            self.ret_all_card = self.dialog.card_ret_all
            self.ret_young_card = self.dialog.card_ret_young
            self.ret_mat_card = self.dialog.card_ret_mat
            self.streak_card = self.dialog.card_streak
            self.active_days_card = self.dialog.card_active_days

            # Titles stay visible in the Deep Dive view
            for card in [self.time_card, self.rev_card, self.ret_all_card, self.ret_young_card, self.ret_mat_card, self.streak_card, self.active_days_card]:
                card.set_title_visible(True)

            self.dialog.stats_container.set_reduced_height_mode(False)

            def on_dash_visibility_changed(key, checked):
                self.dialog.addon_config.set_value(key, checked)
                if hasattr(self.dialog, "update_dashboard_visibility"):
                    self.dialog.update_dashboard_visibility()

            self.dialog.stats_container.set_visibility_callback(on_dash_visibility_changed)
            if hasattr(self.dialog, "update_dashboard_visibility"):
                self.dialog.update_dashboard_visibility()

        totals_payload = {
            "time": time_hours,
            "rev": reviews,
            "pass": row_data.get("passed", 0),
            "pass_young": pass_young,
            "rev_young": rev_young,
            "pass_mat": pass_mat,
            "rev_mat": rev_mat,
            "streak_current": row_data.get("streak_current", 0),
            "active_days": row_data.get("active_days", 0),
            "again": row_data.get("again"),
        }
        try:
            from ...widgets.pinned.context_access import get_pinned_context
            from ...widgets.stats_cards import deck_state_from_context

            totals_payload.update(deck_state_from_context(
                get_pinned_context(deck_id, Period.TOTAL, cfg=self.dialog.addon_config, allow_slow_ops=isinstance(deck_id, list))
            ))
        except Exception:
            log_swallowed()
        # Kept for the zoom updates, which rebuild the values from a history slice.
        self._stats_state = {k: totals_payload.get(k) for k in ("counts", "future_due", "fsrs")}
        # Day-level cards read the daily history, which only matches the window's own range.
        if time_span is None or int(time_span) == int(getattr(self, "last_history_range", time_span)):
            day_totals = build_dashboard_history_totals(getattr(self, "last_history_data", None) or [])
            if day_totals["days_in_period"]:
                for key in ("days_in_period", "period_active_days", "longest_streak", "best_day"):
                    totals_payload[key] = day_totals[key]
                if totals_payload["again"] is None:
                    totals_payload["again"] = day_totals["again"]
        stat_values = build_dashboard_stat_values(
            totals_payload,
            use_decimal=True,
            hrs_unit="h",
            min_unit=" min",
            prec=prec,
        )
        apply_dashboard_stat_values(self.dialog, stat_values, refresh=False)

        available_width = self.dialog.width()
        if available_width > 0:
             self.dialog.stats_container.update_layout(available_width)

        return None

    def _update_stats_from_history(self, history_slice, part=None):
        return update_stats_from_history(self, history_slice, part)

