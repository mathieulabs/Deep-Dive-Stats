# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors



def prepare_other_defs_and_reflow(
    manager,
    other_defs,
    pinned_conf,
    review_return_light_mode,
    should_full_rebuild,
    deck_id,
):
    if review_return_light_mode:
        # During review-return phase B, update non-heatmap charts first.
        other_charts = [d for d in other_defs if d.get("type") != "heatmap"]
        heatmap_defs = [d for d in other_defs if d.get("type") == "heatmap"]
        other_defs = other_charts + heatmap_defs

    chart_probe_sig = tuple(
        (
            d.get("id"),
            d.get("type"),
            int(d.get("row_num", 0) or 0),
            int(d.get("col_offset", 0) or 0),
        )
        for d in other_defs
    )
    manager._last_chart_probe_sig = chart_probe_sig

    chart_reflow_sig = (
        chart_probe_sig,
        bool(manager._is_deck_browser),
        int(deck_id) if deck_id is not None else None,
    )
    should_animate_chart_reflow = bool(
        not should_full_rebuild
        and manager._last_chart_reflow_sig is not None
        and manager._last_chart_reflow_sig != chart_reflow_sig
    )
    manager._last_chart_reflow_sig = chart_reflow_sig
    return other_defs, should_animate_chart_reflow



