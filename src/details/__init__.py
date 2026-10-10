# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import importlib

# Lazy exports (PEP 562): importing DetailedStatsDialog eagerly pulled in the whole Deep Dive UI at
# every Anki startup, because main_menu.manager lives under this package. Names are imported on
# first use instead.
_LAZY_IMPORTS = {
    "DetailedStatsDialog": (".dialog", "DetailedStatsDialog"),
    "DetailedStatsConfigDialog": (".ui.config", "DetailedStatsConfigDialog"),
    "DeckSettingsDialog": (".ui.config", "DeckSettingsDialog"),
}


def __getattr__(name):
    target = _LAZY_IMPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_path, attr_name = target
    module = importlib.import_module(module_path, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals().keys()) | set(_LAZY_IMPORTS.keys()))


def open_details_dialog():
    """Open Details via overview singleton flow."""
    from ..startup import on_show_details

    return on_show_details()


__all__ = [
    "DeckSettingsDialog",
    "DetailedStatsConfigDialog",
    "DetailedStatsDialog",
    "open_details_dialog",
]
