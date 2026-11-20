# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .src import pyc_cache

pyc_cache.install(__name__)  # before the add-on's other imports: their .pyc where Python writes none (Kioku)

from .src import startup  # noqa: E402

startup.register_hooks()
