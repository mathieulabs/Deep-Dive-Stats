# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Shared helper for FSRS chart builders (stability, difficulty, retrievability)."""

from ..utils import _addon_config
from . import HistoryProvider, Period
from ..shared.context import get_pinned_context_value
from .....logic.data.section_fetchers import fetch_section_data
from .....logic.data.section_fallbacks import resolve_fsrs_payload


def fetch_fsrs_data(deck_id, cfg=None, fail_if_not_cached=False):
    """Fetch FSRS stats for a given deck, cache first then SQL fallback."""
    config = cfg or _addon_config()

    # Concrete decks: query with a did_limit built from the deck and its children.
    # This matches the Deep Dive folder behavior and avoids stale cache snapshots
    # for FSRS payloads.
    if isinstance(deck_id, int) and deck_id not in (-1, 0):
        did_limit = HistoryProvider._get_did_limit(config, deck_id)
        return fetch_section_data(
            config,
            "fsrs",
            deck_id=deck_id,
            is_deleted=False,
            did_limit=did_limit,
        ) or {}

    _, fsrs = get_pinned_context_value(
        deck_id,
        Period.TOTAL,
        "fsrs",
        cfg=config,
        fail_if_not_cached=fail_if_not_cached,
    )

    resolved_fsrs = resolve_fsrs_payload(
        {"fsrs": fsrs} if fsrs is not None else None,
        fetcher=None,
        require_stability=False,
    )
    if resolved_fsrs is not None:
        return resolved_fsrs

    # Non-blocking UI pass: don't mix in SQL fallback snapshots.
    # Wait for cache-ready callback so both FSRS charts consume the same source.
    if fail_if_not_cached:
        return None

    res = fetch_section_data(config, "fsrs", deck_id=deck_id, is_deleted=False)
    return res



def build_simple_fsrs_chart(chart_cls, data_key, title, widget_def, deck_id, parent=None, cfg=None):
    """Pinned FSRS chart without extra header controls (Difficulty, Retrievability)."""
    from ..wrapper import _wrap
    from . import ADAPTIVE_CHART_BINNING, Config, pinned_title
    from ....common import apply_chart_display_config, create_chart_header_for_chart

    cfg = _addon_config() if cfg is None else cfg
    adaptive_binning = cfg.config.get(ADAPTIVE_CHART_BINNING, True)
    fsrs_data = fetch_fsrs_data(deck_id, cfg, fail_if_not_cached=True) or {}

    chart = chart_cls(fsrs_data.get(data_key, {}), parent=parent, adaptive_binning=adaptive_binning)
    chart.binning_override = widget_def.get("binning_override", None)
    apply_chart_display_config(
        chart,
        opacity=widget_def.get("chart_opacity", 100),
        line_opacity=widget_def.get("line_opacity"),
        bar_gradient=widget_def.get("bar_gradient"),
        show_grid=widget_def.get("show_grid"),
        minimum_height=120,
    )

    label = pinned_title(widget_def, title)
    header_widget, _, _, _ = create_chart_header_for_chart(
        chart,
        cfg,
        Config.DEEP_DIVE_PINNED_SHOW_BOTTOM_STATS,
        Config.DEEP_DIVE_PINNED_SHOW_STATS,
        parent=parent,
        title=label,
        title_object_name="pinned_header",
        include_when_no_header_stats=False,
    )

    return _wrap(chart, label.upper() if not header_widget else None,
                 header_widget=header_widget,
                 widget_id=widget_def["id"],
                 saved_w=widget_def.get("width"),
                 saved_h=widget_def.get("height"),
                 parent=parent)


def update_simple_fsrs_chart(chart, data_key, widget_def, deck_id, fail_if_not_cached=False, cfg=None):
    from . import ADAPTIVE_CHART_BINNING
    from ....common import refresh_parent_chart_header_stats

    fsrs_data = fetch_fsrs_data(deck_id, cfg, fail_if_not_cached=fail_if_not_cached)
    if fsrs_data is None:
        return False
    if hasattr(chart, "update_data"):
        if cfg is None:
            cfg = _addon_config()
        adaptive_binning = cfg.config.get(ADAPTIVE_CHART_BINNING, True)

        chart.binning_override = widget_def.get("binning_override", None)
        chart.update_data(fsrs_data.get(data_key, {}), adaptive_binning=adaptive_binning)

        refresh_parent_chart_header_stats(chart)

        return True
    return False


def add_fsrs_filter_radio(chart, widget_def, header_widget, header_lay):
    """Young/Mature/All style filter radio shown in the header of Stability and Review Intervals."""
    from ..utils import _make_radio_group
    from ....common import (
        create_fsrs_filter_group,
        default_fsrs_filter_idx,
        refresh_parent_chart_header_stats,
        resolve_fsrs_filter_choice,
        resolve_fsrs_filters,
    )

    def on_filter_applied(idx):
        from ...store.registry import WidgetRegistry
        WidgetRegistry.update_setting(widget_def["id"], "view_filter_idx", idx)
        refresh_parent_chart_header_stats(chart)

    fsrs_modes, fsrs_short, _ = resolve_fsrs_filters(widget_def.get("filter_modes"))
    default_idx, initial_mode = resolve_fsrs_filter_choice(widget_def.get("view_filter_idx"), modes=fsrs_modes)
    chart.set_view_filter(initial_mode)

    radio = create_fsrs_filter_group(
        chart,
        labels=fsrs_short,
        resolved_idx=default_idx,
        make_radio_group=_make_radio_group,
        parent=header_widget,
        on_idx_applied=on_filter_applied,
        modes=fsrs_modes,
        default_idx=default_fsrs_filter_idx(fsrs_modes),
    )
    header_lay.addWidget(radio)
