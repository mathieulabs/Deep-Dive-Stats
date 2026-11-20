# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""A one-line banner in the Deep Dive window (drawn by the page, app.js) asking people who use the add-on to rate it.

It only shows after RATE_MIN_DAYS days and RATE_MIN_OPENS openings of the window, then
again RATE_GAPS_DAYS later (30, then 90 days), so three times at most. A showing only
counts once the banner stayed on screen RATE_SEEN_MS, or "Later" was clicked. "Rate" and
"Don't ask again" end it for good. The state is shared by all profiles and survives
updates (user_files).
"""

import time


from ...logic.user_state import load_state, save_state
from ....i18n import N_

# The banner's texts are the page's (app.js); this one check_translations cannot read there (a quote inside quotes).
_PAGE_TEXTS = (N_("Don't ask again"),)

RATE_MIN_DAYS = 10
RATE_MIN_OPENS = 10
RATE_GAPS_DAYS = (30, 90)
RATE_MAX_SHOWS = len(RATE_GAPS_DAYS) + 1
RATE_SEEN_MS = 12000

_DAY = 86400


def _load():
    return load_state("rate_prompt.json")


def _save(state):
    save_state("rate_prompt.json", state)


def _should_show(state, now):
    if state.get("preview"):
        return True
    if state.get("done") or state.get("shows", 0) >= RATE_MAX_SHOWS:
        return False
    return (
        state.get("opens", 0) >= RATE_MIN_OPENS
        and now - state.get("first_seen", now) >= RATE_MIN_DAYS * _DAY
        and now >= state.get("snooze_until", 0)
    )


def mark_rated():
    """The rating page was opened (toolbar menu, or the banner's Rate), or "Don't ask again": no need to ask anymore."""
    state = _load()
    state["done"] = True
    _save(state)


def preview_next_open():
    """Developer tool: show the banner the next time the Deep Dive window opens."""
    state = _load()
    state["preview"] = True
    _save(state)


def window_opened():
    """One more opening of the Deep Dive window counted. The banner's options ({preview, seen_ms}) when it is due, else None."""
    now = time.time()
    state = _load()
    state.setdefault("first_seen", now)
    state["opens"] = state.get("opens", 0) + 1
    show = _should_show(state, now)
    preview = bool(state.pop("preview", None)) if show else False
    _save(state)
    return {"preview": preview, "seen_ms": RATE_SEEN_MS} if show else None


def count_show():
    """The banner was seen (on screen RATE_SEEN_MS, or "Later" clicked): the next one waits for the next gap."""
    state = _load()
    shows = state.get("shows", 0) + 1
    state["shows"] = shows
    if shows <= len(RATE_GAPS_DAYS):
        state["snooze_until"] = time.time() + RATE_GAPS_DAYS[shows - 1] * _DAY
    _save(state)
