# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Compiled files (.pyc) for the add-on's own modules when Python is told not to write any.

Some hosts (Kioku on Android) start Python with sys.dont_write_bytecode on: every start then compiles again all the
code the add-on imports, a large part of its first second on a phone. Python still reads .pyc files in that mode, it
only never writes them; this loader writes them, for the add-on's modules only (its own folder), the way Python
would (timestamp .pyc in __pycache__). Nothing changes where Python writes them itself (Anki on a computer)."""

import os
import sys
from importlib.abc import MetaPathFinder
from importlib.machinery import PathFinder, SourceFileLoader

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the add-on's folder


class _Loader(SourceFileLoader):
    def source_to_code(self, data, path, *args, **kwargs):
        code = super().source_to_code(data, path, *args, **kwargs)
        try:
            import importlib.util
            from importlib import _bootstrap_external as be

            st = os.stat(path)
            pyc = be._code_to_timestamp_pyc(code, st.st_mtime, st.st_size)
            self.set_data(importlib.util.cache_from_source(path), pyc)  # makes __pycache__, writes atomically
        except Exception:
            pass  # a read-only folder, a Python without these helpers: compiled each time, as before
        return code


class _Finder(MetaPathFinder):
    def __init__(self, package):
        self._prefix = package + "."

    def find_spec(self, fullname, path=None, target=None):
        if not fullname.startswith(self._prefix):
            return None
        spec = PathFinder.find_spec(fullname, path, target)
        if spec is None or type(spec.loader) is not SourceFileLoader or not spec.origin:
            return spec
        if not os.path.abspath(spec.origin).startswith(_DIR + os.sep):
            return spec
        spec.loader = _Loader(fullname, spec.origin)
        return spec


def install(package):
    """From the add-on's __init__ (package: its __name__), before its other imports."""
    if not sys.dont_write_bytecode or any(isinstance(f, _Finder) for f in sys.meta_path):
        return
    sys.meta_path.insert(0, _Finder(package))
