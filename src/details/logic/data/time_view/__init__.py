# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .loader import load_stats_data
from .static import (
    get_time_view_static_bundle,
)

__all__ = [
    "load_stats_data",
    "get_time_view_static_bundle",
]
