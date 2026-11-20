# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
__all__ = ["apply_style"]


def __getattr__(name):
    if name == "apply_style":
        from .styler import apply_style

        return apply_style
    raise AttributeError(name)
