# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Small JSON files the add-on keeps about itself in user_files (the guided tour seen, the
rate prompt shown...). A missing or unreadable file reads as {}; a file is written whole
or not at all."""

import json
import os

from ...const.addon_dir import addon_removed
from .logger import log_swallowed


def state_path(name):
    addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    return os.path.join(addon_dir, "user_files", name)


def load_state(name):
    try:
        with open(state_path(name), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        log_swallowed()
        return {}


def save_state(name, state):
    if addon_removed():
        return
    try:
        path = state_path(name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, path)
    except Exception:
        log_swallowed()
