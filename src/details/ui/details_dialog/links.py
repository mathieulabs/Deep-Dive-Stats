# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""External links used by the Deep Dive toolbar.

SUPPORT_URL: Ko-fi page (heart button). RATE_URL: AnkiWeb's rating form (thumbs-up button
and rating banner).
GITHUB_URL: project page. A button is only shown when its URL is set.
"""
from ...logic.logger import log_swallowed

SUPPORT_URL = "https://ko-fi.com/mathieu_"
RATE_URL = "https://ankiweb.net/shared/review/1498951013"  # AnkiWeb's own "Rate This" link
GITHUB_URL = "https://github.com/mathieulabs/Deep-Dive-Stats"


def open_link(url):
    if not url:
        return
    try:
        from aqt.qt import QDesktopServices, QUrl
        QDesktopServices.openUrl(QUrl(url))
    except Exception:
        log_swallowed()
