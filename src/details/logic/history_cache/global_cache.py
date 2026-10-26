# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .context import ContextMixin
from .core import GlobalHistoryCacheCore
from .init import InitMixin
from .population import PopulationMixin
from .refresh import RefreshMixin
from .storage import StorageMixin
from .warmup import WarmupMixin


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
