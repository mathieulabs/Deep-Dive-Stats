# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .shared import Period
from .ops.history_fetch import fetch_history as fetch_history_impl


class HistoryFetchMixin:
    @staticmethod
    def fetch_history(
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
        return fetch_history_impl(
            HistoryProvider,
            addon_config,
            deck_id=deck_id,
            range_type=range_type,
            is_deleted=is_deleted,
            override_start_ms=override_start_ms,
            override_end_ms=override_end_ms,
            override_bin_ms=override_bin_ms,
            minimal=minimal,
            did_limit=did_limit,
            custom_days=custom_days,
            custom_type=custom_type,
            start_date_str=start_date_str,
            end_date_str=end_date_str,
            align_with_added=align_with_added,
        )

