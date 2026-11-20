# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Click a chart bar or slice to show its cards in the Anki browser (like native Anki stats)."""


_PIE_QUERIES = {
    "new": "is:new -is:suspended -is:buried",
    "learn": "is:learn -is:review -is:suspended -is:buried",
    "relearn": "is:learn is:review -is:suspended -is:buried",
    "young": "is:review -is:learn prop:ivl<21 -is:suspended -is:buried",
    "mature": "is:review -is:learn prop:ivl>=21 -is:suspended -is:buried",
    "suspended": "is:suspended",
    "buried": "is:buried",
}


