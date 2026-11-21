# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The Deep Dive window's base colors (background, surface, borders, text, accent) from the theme palette, read by
web_ui/theme.py and the backdrop settings."""

from .. import ThemePalettes


def _colors(is_dark, palette):
    if palette is None and is_dark:
        palette = ThemePalettes.ANKI_LIKE_PALETTE.copy()
    if palette is not None:
        return {
            "bg": palette["bg_root"],
            "surface": palette["bg_surface"],
            "border": palette["border_subtle"],
            "border_strong": palette["border_strong"],
            "text": palette["text_primary"],
            "muted": palette["text_secondary"],
            "accent": palette["accent"],
            "accent_hover": palette.get("accent_hover", palette["accent"]),
        }
    light = ThemePalettes.ANKI_LIKE_PALETTE_LIGHT
    return {
        "bg": light["bg_root"],
        "surface": light["bg_surface"],
        "border": light["border_subtle"],
        "border_strong": light["border_strong"],
        "text": light["text_primary"],
        "muted": light["text_secondary"],
        "accent": light["accent"],
        "accent_hover": light["accent_hover"],
    }


def _mix(base_hex, over_hex, k):
    b = base_hex.lstrip("#")
    o = over_hex.lstrip("#")
    if len(b) == 3:
        b = "".join(ch * 2 for ch in b)
    if len(o) == 3:
        o = "".join(ch * 2 for ch in o)
    out = []
    for i in (0, 2, 4):
        bv = int(b[i:i + 2], 16)
        ov = int(o[i:i + 2], 16)
        out.append(int(round(bv + (ov - bv) * k)))
    return "#%02x%02x%02x" % tuple(out)

