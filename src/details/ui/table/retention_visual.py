# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Retention visual bar toggle helper."""
from aqt import mw

from .. import Config
from ....config import ConfigManager

_KEYS = {
    "all": Config.RETENTION_VISUAL_ALL,
    "young": Config.RETENTION_VISUAL_YOUNG,
    "mature": Config.RETENTION_VISUAL_MATURE,
}


def retention_visual_on(kind):
    """kind is 'all', 'young' or 'mature'."""
    try:
        return bool(ConfigManager(mw).config.get(_KEYS[kind], False))
    except Exception:
        return False
