# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Week by Hour: when you review in the week (7 days x 24 hours)."""

from .....i18n import N_

LABEL = N_("Week by Hour")


def fetch_counts(cfg, deck_id, is_deleted, days, filtered=True):
    """{(weekday 0 Monday .. 6 Sunday, hour 0-23): reviews} of the period of the day rows (filtered=False: the
    reviews of filtered decks, revlog type 3, left out)."""
    from ....logic.metrics.review_buckets import did_limit, range_from_days, week_hour_counts

    rng = range_from_days(days)
    if not rng:
        return {}
    return week_hour_counts(did_limit(cfg, deck_id, is_deleted) + ("" if filtered else " AND revlog.type != 3"), *rng)
