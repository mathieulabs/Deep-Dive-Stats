# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations

from typing import TypedDict


class DataColorsDict(TypedDict, total=False):
    Color_Time: str
    Color_Avg_Time: str
    Color_Reviews: str
    Color_Retention: str
    Color_Mature: str
    Color_Streak: str
    Color_Active_Days: str
    Color_Learn: str
    Color_Young: str
    Color_Relearn: str
    Color_Cram: str
    Color_New: str
    Color_Suspended: str
    Color_Buried: str
    Color_Again: str
    Color_Hard: str
    Color_Good: str
    Color_Easy: str
    Color_Bar: str
    Color_Future_Due: str
    Color_Backlog: str
    Color_Deleted: str
    Color_Gradient_Low: str
    Color_Gradient_High: str
    Heatmap_Color: str
