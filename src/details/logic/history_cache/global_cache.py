# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .context import ContextMixin
from .core import GlobalHistoryCacheCore
from .init import InitMixin
from .population import PopulationMixin
from .refresh import RefreshMixin
from .storage import StorageMixin
from .warmup import WarmupMixin
import sys


class GlobalHistoryCache(
    InitMixin,
    RefreshMixin,
    WarmupMixin,
    ContextMixin,
    PopulationMixin,
    StorageMixin,
    GlobalHistoryCacheCore,
):
    pass


for _mod in ("core", "init", "context", "refresh", "population", "storage", "warmup"):
    _full_name = f"{__package__}.{_mod}"
    _loaded = sys.modules.get(_full_name)
    if _loaded is not None:
        _loaded.GlobalHistoryCache = GlobalHistoryCache

