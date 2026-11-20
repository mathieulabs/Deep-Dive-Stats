# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""What the web pages write to debug.log.

Errors always go there. The timing and animation traces (DD.trace in the pages, trace() here) are for development:
they are written in a source checkout only, so a user's log keeps what helps a bug report."""

from ..details.logic.logger import log_batch, log_warn

def is_dev():
    from ..config import is_dev_build

    return is_dev_build()


def dev_flag():
    """Script text that turns on the page's traces (DD.dev) in a source checkout; empty for users."""
    return "DD.dev=true;" if is_dev() else ""


def trace(message):
    """A development trace (timings, steps of a flow): written in a source checkout only."""
    if is_dev():
        log_warn(message, tag="WEB")


def page_log(text):
    """Lines a page sent with DD.log or DD.trace (DD.trace sends nothing outside a source checkout)."""
    # a page sends its traces in batches, one line each, written to the file at once
    with log_batch():
        for line in str(text).split(chr(10)):
            if line:
                log_warn(line, tag="WEB")
