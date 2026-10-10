# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Import smoke test that runs without Anki.

Fakes just enough of aqt and anki to load the add-on the way Anki does, then
checks that the entry points resolve and that every module under src/ imports.
It catches missing names, circular imports and bad relative paths, not runtime
behavior.

    python dev_tools/check_import_graph.py

Run it after touching an __init__.py or moving files.
"""

import atexit
import importlib
import importlib.abc
import importlib.util
import os
import shutil
import sys
import tempfile
import types
from unittest.mock import MagicMock


# Stand-in for Qt classes: works as a base class, is callable, and any
# attribute access returns another stand-in instead of raising.

class _AutoMeta(type):
    _cache = {}

    def __getattr__(cls, name):
        key = (cls, name)
        if key not in _AutoMeta._cache:
            base = cls if cls is not object else _Auto
            _AutoMeta._cache[key] = _AutoMeta(name, (base,), {})
        return _AutoMeta._cache[key]


class _Auto(metaclass=_AutoMeta):
    def __init__(self, *a, **k):
        pass

    def __getattr__(self, name):
        return _Auto()

    def __call__(self, *a, **k):
        return _Auto()

    def setter(self, fn=None):
        return fn if fn else (lambda f: f)

    def getter(self, fn=None):
        return fn if fn else (lambda f: f)

    def connect(self, *a, **k):
        pass

    def append(self, *a, **k):
        pass

    def remove(self, *a, **k):
        pass

    def emit(self, *a, **k):
        pass

    def __or__(self, other):
        return self

    def __eq__(self, other):
        return False

    def __hash__(self):
        return id(self)

    def __bool__(self):
        return True

    def __iter__(self):
        return iter([])

    def __getitem__(self, key):
        return _Auto()

    def __int__(self):
        return 0

    def __index__(self):
        return 0

    def __str__(self):
        return ""

    def __len__(self):
        return 0


class AutoAttrModule(types.ModuleType):
    """Module stand-in where any missing attribute auto-vivifies instead of
    raising AttributeError. Used for real anki/aqt submodules we haven't
    hand-written a stub for (unknown constants, helper functions, etc.)."""

    def __getattr__(self, name):
        return _AutoMeta(name, (_Auto,), {})


class AutoPackageFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Catch-all for anki.*/aqt.* submodules with no explicit stub."""

    def __init__(self, prefixes):
        self.prefixes = prefixes

    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == p or fullname.startswith(p + ".") for p in self.prefixes):
            return importlib.util.spec_from_loader(fullname, self, is_package=True)
        return None

    def create_module(self, spec):
        mod = AutoAttrModule(spec.name)
        mod.__path__ = []  # pretend to be a package so deeper submodules resolve too
        return mod

    def exec_module(self, module):
        pass


def _install_stubs():
    sys.meta_path.insert(0, AutoPackageFinder(["anki", "aqt"]))

    anki_buildinfo = types.ModuleType("anki.buildinfo")
    anki_buildinfo.version = "26.09"
    sys.modules["anki.buildinfo"] = anki_buildinfo
    anki_pkg = AutoAttrModule("anki")
    anki_pkg.__path__ = []
    sys.modules["anki"] = anki_pkg

    class QtModule(types.ModuleType):
        def __getattr__(self, name):
            return _AutoMeta(name, (_Auto,), {})

    aqt_qt = QtModule("aqt.qt")
    aqt_qt.QT_VERSION_STR = "6.9.1"
    aqt_qt.PYQT_VERSION_STR = "6.9.1"

    aqt_pkg = types.ModuleType("aqt")
    aqt_pkg.mw = MagicMock(name="mw")
    # Config files are written under a throwaway folder, not next to the add-on.
    scratch = tempfile.mkdtemp(prefix="deep_dive_check_")
    atexit.register(shutil.rmtree, scratch, True)
    aqt_pkg.mw.addonManager.addonsFolder.return_value = scratch
    aqt_pkg.mw.addonManager.addonFromModule.return_value = "deep_dive_check"
    aqt_pkg.mw.pm.name = "check"
    aqt_pkg.gui_hooks = MagicMock(name="gui_hooks")
    aqt_pkg.AnkiQt = _AutoMeta("AnkiQt", (_Auto,), {})
    aqt_pkg.qt = aqt_qt
    aqt_pkg.appVersion = "26.09"
    aqt_pkg.__path__ = []

    aqt_theme = types.ModuleType("aqt.theme")
    aqt_theme.theme_manager = MagicMock(name="theme_manager")

    sys.modules["aqt"] = aqt_pkg
    sys.modules["aqt.qt"] = aqt_qt
    sys.modules["aqt.theme"] = aqt_theme
    aqt_main = types.ModuleType("aqt.main")
    aqt_main.AnkiQt = aqt_pkg.AnkiQt
    sys.modules["aqt.main"] = aqt_main


def main():
    _install_stubs()

    addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    module_name = os.path.basename(addon_dir)  # matches how Anki names the addon module
    spec = importlib.util.spec_from_file_location(
        module_name,
        os.path.join(addon_dir, "__init__.py"),
        submodule_search_locations=[addon_dir],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    failures = []

    def check(label, fn):
        try:
            result = fn()
            print(f"OK   {label}" + (f" -> {result}" if result is not None else ""))
        except Exception as e:  # noqa: BLE001
            import traceback

            traceback.print_exc()
            print(f"FAIL {label}: {e!r}")
            failures.append(label)

    check("addon startup (register_hooks)", lambda: (spec.loader.exec_module(module), None)[1])
    check(
        "lazy DetailedStatsDialog import",
        lambda: sys.modules[f"{module_name}.src.details"].DetailedStatsDialog,
    )
    check(
        "lazy chart widget import (ActivityChart)",
        lambda: sys.modules[f"{module_name}.src.details.widgets"].ActivityChart,
    )
    check(
        "history_cache import (the exact path that crashed on sync_did_finish)",
        lambda: importlib.import_module(f"{module_name}.src.details.logic.history_cache").GlobalHistoryCache,
    )
    check(
        "settings dialog import",
        lambda: importlib.import_module(f"{module_name}.src.details.ui.config").DetailedStatsConfigDialog,
    )

    def import_every_module():
        bad = []
        count = 0
        src_dir = os.path.join(addon_dir, "src")
        for base, dirs, names in os.walk(src_dir):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in names:
                if not name.endswith(".py") or name == "__init__.py":
                    continue
                rel = os.path.relpath(os.path.join(base, name[:-3]), addon_dir)
                dotted = module_name + "." + rel.replace(os.sep, ".")
                count += 1
                try:
                    importlib.import_module(dotted)
                except Exception as e:  # noqa: BLE001
                    bad.append(f"{dotted}: {e!r}")
        if bad:
            raise RuntimeError(f"{len(bad)} module(s) failed to import:\n" + "\n".join(bad[:20]))
        return f"{count} modules"

    check("import every module", import_every_module)

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
        sys.exit(1)
    print("All import-graph checks passed.")


if __name__ == "__main__":
    main()
