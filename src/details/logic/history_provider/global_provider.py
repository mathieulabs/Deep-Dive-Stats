# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .cards import CardsMixin
from .context import ContextMixin
from .core import HistoryProviderCore
from .did_limit import DidLimitMixin
from .history import HistoryFetchMixin
from .stats import StatsMixin
import sys


class HistoryProvider(
    DidLimitMixin,
    HistoryFetchMixin,
    StatsMixin,
    CardsMixin,
    ContextMixin,
    HistoryProviderCore,
):
    pass


for _mod in ("did_limit", "history", "stats", "cards", "context"):
    _full_name = f"{__package__}.{_mod}"
    _loaded = sys.modules.get(_full_name)
    if _loaded is not None:
        _loaded.HistoryProvider = HistoryProvider

