# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .cards import CardsMixin
from .context import ContextMixin
from .core import HistoryProviderCore
from .did_limit import DidLimitMixin
from .history import HistoryFetchMixin
from .stats import StatsMixin


class HistoryProvider(
    DidLimitMixin,
    HistoryFetchMixin,
    StatsMixin,
    CardsMixin,
    ContextMixin,
    HistoryProviderCore,
):
    pass
