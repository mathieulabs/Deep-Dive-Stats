# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt import mw

from ....ui import ConfigManager


def addon_name(module_name):
    return mw.addonManager.addonFromModule(module_name)


def addon_meta(module_name):
    """Add-on meta with "config" replaced by the active per-profile config."""
    meta = dict(mw.addonManager.addonMeta(addon_name(module_name)))
    meta["config"] = ConfigManager(mw).config
    return meta


def addon_config(module_name):
    return ConfigManager(mw).config


def write_addon_config(module_name, conf):
    manager = ConfigManager(mw)
    manager.config = dict(conf or {})
    manager.write_config()


def write_addon_config_vals(module_name, updates):
    manager = ConfigManager(mw)
    manager.write_config_vals(dict(updates or {}))
