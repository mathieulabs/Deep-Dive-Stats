# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Totals aggregation helpers."""

def calculate_totals(results, prev_stats_map, deck_limits, remaining_new_map, bin_labels, retention_maps, bin_count):
    """
    Calculate aggregated totals from all deck results.
    """
    t_time = 0
    t_rev = 0
    t_pass = 0
    t_rev_young = 0
    t_pass_young = 0
    t_rev_mat = 0
    t_pass_mat = 0
    t_again = 0
    t_hard = 0
    t_good = 0
    t_easy = 0

    t_limit = 0
    t_remaining = 0
    t_max_days = 0

    for res in results:
            # 1: time, 2: reviews, 3: passed, 4: pass_young, 5: rev_young, 6: pass_mat, 7: rev_mat, 8: again, 9: hard, 10: good, 11: easy
            t_time += (res[1] or 0) / 1000 / 60 / 60
            t_rev += (res[2] or 0)
            t_pass += (res[3] or 0)
            t_pass_young += (res[4] or 0)
            t_rev_young += (res[5] or 0)
            t_pass_mat += (res[6] or 0)
            t_rev_mat += (res[7] or 0)
            t_again += (res[8] or 0)
            t_hard += (res[9] or 0)
            t_good += (res[10] or 0)
            t_easy += (res[11] or 0)

    # Forecast over every deck, as in the deck view (see core.forecast).
    from ..core.forecast import forecast_parts

    t_limit, t_max_days, t_remaining = forecast_parts(
        [d for d in set(deck_limits) | set(remaining_new_map) if d is not None], deck_limits, remaining_new_map
    )

    t_prev_time = 0
    t_prev_rev = 0
    t_prev_pass = 0
    t_prev_rev_young = 0
    t_prev_pass_young = 0
    t_prev_rev_mat = 0
    t_prev_pass_mat = 0

    for pr in prev_stats_map.values():
        t_prev_time += (pr[1] or 0) / 1000 / 60 / 60
        t_prev_rev += (pr[2] or 0)
        t_prev_pass += (pr[3] or 0)
        t_prev_pass_young += (pr[4] or 0)
        t_prev_rev_young += (pr[5] or 0)
        t_prev_pass_mat += (pr[6] or 0)
        t_prev_rev_mat += (pr[7] or 0)

    totals = {
        "time": t_time, "rev": t_rev, "pass": t_pass,
        "rev_young": t_rev_young, "pass_young": t_pass_young,
        "rev_mat": t_rev_mat, "pass_mat": t_pass_mat,
        "again": t_again, "hard": t_hard, "good": t_good, "easy": t_easy,
        "limit": t_limit, "remaining": t_remaining, "max_days": t_max_days,
        "prev_time": t_prev_time, "prev_rev": t_prev_rev, "prev_pass": t_prev_pass,
        "prev_rev_young": t_prev_rev_young, "prev_pass_young": t_prev_pass_young,
        "prev_rev_mat": t_prev_rev_mat, "prev_pass_mat": t_prev_pass_mat,
        "activity_labeled": [],
        "retention_bins": {"all": [], "young": [], "mature": []},
    }
    return totals


