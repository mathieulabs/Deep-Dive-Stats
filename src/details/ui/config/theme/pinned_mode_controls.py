# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations


from ... import Config



def get_pinned_theme_mode_from_config(conf: dict | None) -> str:
    conf = conf if isinstance(conf, dict) else {}
    use_active = bool(conf.get(Config.PINNED_USE_ACTIVE_THEME, False))
    use_separate = bool(conf.get(Config.PINNED_USE_SEPARATE_THEME, False))
    if not use_active:
        return "native"
    if use_separate:
        return "separate"
    return "linked"


def set_pinned_theme_mode_in_config(dialog, mode: str) -> None:
    mode = str(mode or "native").strip().lower()
    if mode == "linked":
        dialog.save_global_config(Config.PINNED_USE_ACTIVE_THEME, True)
        dialog.save_global_config(Config.PINNED_USE_SEPARATE_THEME, False)
        return
    if mode == "separate":
        dialog.save_global_config(Config.PINNED_USE_ACTIVE_THEME, True)
        dialog.save_global_config(Config.PINNED_USE_SEPARATE_THEME, True)
        return
    dialog.save_global_config(Config.PINNED_USE_ACTIVE_THEME, False)
    dialog.save_global_config(Config.PINNED_USE_SEPARATE_THEME, False)









