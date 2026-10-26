# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Excluded decks as seen by the cache aggregates (all-decks totals)."""
from ..logger import log_swallowed


def excluded_dids():
    """Set of excluded home deck ids (empty on any error)."""
    try:
        from aqt import mw
        from ....config import ConfigManager
        from ....const import Config
        from ....utils import split_excluded
        ids, deleted = split_excluded(ConfigManager(mw).config.get(Config.EXCLUDED_DECKS, []))
        out = set(ids)
        if deleted:
            out.add(-1)  # deleted cards pseudo deck
        return out
    except Exception:
        return set()


def exclusion_signature():
    sig = sorted(excluded_dids())
    try:
        from ....utils import excluded_day_rules
        sig += [f"d:{a}-{b}-{sorted(d) if d else ''}" for a, b, d in excluded_day_rules()]
        from ....utils import rollover_hour
        # Daily bins follow the rollover hour: a new hour makes the saved cache stale.
        sig.append(f"r:{rollover_hour()}")
        # And the time zone: days counted in another one (travel, a new computer) are shifted.
        sig.append(f"tz:{_timezone_signature()}")
    except Exception:
        log_swallowed()
    return sig


def _timezone_signature():
    """UTC offsets (minutes) in mid-January and mid-July of this year: differs between
    time zones, including their summer time rules."""
    from datetime import datetime

    year = datetime.now().year
    return ",".join(
        str(int(datetime(year, month, 15, 12).astimezone().utcoffset().total_seconds() // 60))
        for month in (1, 7)
    )


def drop_total_targets(targets, did, excluded):
    """Remove the all-decks keys of `targets` when `did` is excluded."""
    if did in excluded:
        targets.discard(None)
        targets.discard("[[TOTAL]]")
    return targets
