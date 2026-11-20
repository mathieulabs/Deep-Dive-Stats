# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import importlib

# Lazy exports (PEP 562). Importing every chart class here would load the whole chart stack
# at Anki startup, because main_menu.manager lives under this package. Names are imported on
# first access instead.
_LAZY_IMPORTS = {
}


def __getattr__(name):
    target = _LAZY_IMPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_path, attr_name = target
    module = importlib.import_module(module_path, __name__)
    value = getattr(module, attr_name)
    # Cache on the module namespace so subsequent access is a normal, fast
    # attribute lookup instead of going through __getattr__ again.
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals().keys()) | set(_LAZY_IMPORTS.keys()))


__all__ = sorted(_LAZY_IMPORTS)
