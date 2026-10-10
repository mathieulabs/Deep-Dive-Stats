# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
def get_pinned_context(
    deck_id,
    range_type,
    cfg=None,
    custom_days=7,
    custom_type="relative",
    start_date_str="",
    end_date_str="",
    fail_if_not_cached=False,
    allow_slow_ops=None,
):
    from .widget_factory.utils import PinnedDataManager, _addon_config

    config = cfg or _addon_config()
    if allow_slow_ops is None:
        allow_slow_ops = not fail_if_not_cached
    ctx = PinnedDataManager.get_context(
        deck_id,
        range_type,
        cfg=config,
        custom_days=custom_days,
        custom_type=custom_type,
        start_date_str=start_date_str,
        end_date_str=end_date_str,
        allow_sync_check=False,
        allow_slow_ops=allow_slow_ops,
    )
    return ctx if isinstance(ctx, dict) else None


def fetch_pinned_context_data(
    deck_id,
    range_type,
    cfg=None,
    custom_days=7,
    custom_type="relative",
    start_date_str="",
    end_date_str="",
    widget_settings=None,
):
    from .widget_factory.utils import _addon_config
    from ...logic.history_provider import HistoryProvider

    config = cfg or _addon_config()
    ctx = HistoryProvider.fetch_pinned_context(
        config,
        deck_id,
        range_type=range_type,
        custom_days=custom_days,
        custom_type=custom_type,
        start_date_str=start_date_str,
        end_date_str=end_date_str,
        widget_settings=widget_settings,
    )
    return ctx if isinstance(ctx, dict) else {}


def get_pinned_contexts(
    deck_id,
    range_types,
    cfg=None,
    *,
    allow_slow_ops=False,
):
    return {
        range_type: get_pinned_context(
            deck_id,
            range_type,
            cfg=cfg,
            allow_slow_ops=allow_slow_ops,
        )
        for range_type in range_types
    }


def get_pinned_context_value(
    deck_id,
    range_type,
    context_key,
    cfg=None,
    custom_days=7,
    custom_type="relative",
    start_date_str="",
    end_date_str="",
    fail_if_not_cached=False,
    allow_slow_ops=None,
):
    ctx = get_pinned_context(
        deck_id,
        range_type,
        cfg=cfg,
        custom_days=custom_days,
        custom_type=custom_type,
        start_date_str=start_date_str,
        end_date_str=end_date_str,
        fail_if_not_cached=fail_if_not_cached,
        allow_slow_ops=allow_slow_ops,
    )
    return ctx, (ctx.get(context_key) if ctx else None)
