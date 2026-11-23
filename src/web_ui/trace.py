# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""What the web pages write to debug.log.

Errors always go there. The timing and animation traces (DD.trace in the pages, trace() here) are for development:
they are written in a source checkout only, so a user's log keeps what helps a bug report."""

from ..details.logic.logger import log_batch, log_warn

def is_dev():
    """Traces on: a source checkout, or a trace test package (dev_tools/build_trace_test.py: a "trace_on" file at
    the add-on's root, the traces without the rest of the dev mode)."""
    from ..config import is_dev_build

    return is_dev_build() or _trace_file()


_TRACE_FILE = []


def _trace_file():
    if not _TRACE_FILE:
        import os

        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        _TRACE_FILE.append(os.path.isfile(os.path.join(root, "trace_on")))
    return _TRACE_FILE[0]


def traces_on():
    """The traces written: in a source checkout, unless DD_NO_TRACE is set (a demo recording: building and sending
    them, hundreds a second in a deck change, costs frames a user's page does not lose). The rest of the dev mode
    (files read again at each opening...) stays."""
    import os

    return is_dev() and not os.environ.get("DD_NO_TRACE")


def dev_flag():
    """Script text that turns on the page's traces (DD.dev) in a source checkout; empty for users."""
    return "DD.dev=true;" if traces_on() else ""


def trace(message):
    """A development trace (timings, steps of a flow): written in a source checkout only."""
    if traces_on():
        log_warn(message, tag="WEB")


def page_log(text):
    """Lines a page sent with DD.log or DD.trace (DD.trace sends nothing outside a source checkout)."""
    # a page sends its traces in batches, one line each, written to the file at once
    with log_batch():
        for line in str(text).split(chr(10)):
            if line:
                log_warn(line, tag="WEB")
