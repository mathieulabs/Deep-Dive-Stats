# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The heatmap's palettes: the levels in several colors instead of shades of one (drawn by web/charts/heatmap.js).

"" is the chosen color (with Multicolor Intensity or not). The presets are fixed color scales (the Review Heatmap
add-on's themes, ColorBrewer, CARTO, matplotlib, Turbo). The user's own gradients are saved in
Heatmap_Custom_Palettes ({"id", "name", "colors": 2 to 12 colors, the least activity first}); one is chosen as
"custom:<id>"."""

from .....i18n import N_

PALETTES = (
    ("", N_("Chosen color")),
    ("lime", N_("Lime")),
    ("olive", N_("Olive")),
    ("ice", N_("Ice")),
    ("magenta", N_("Magenta")),
    ("flame", N_("Flame")),
    ("rainbow", N_("Rainbow")),
    ("ocean", N_("Ocean")),
    ("sunset", N_("Sunset")),
    ("viridis", N_("Viridis")),
)
KEYS = tuple(p[0] for p in PALETTES)
CUSTOM = "custom:"
# a new gradient's colors when nothing else gives them: low, middle, high activity (ColorBrewer Blues)
DEFAULT_COLORS = ("#c6dbef", "#6baed6", "#08519c")
# 12: as many as the richest preset (Rainbow); a new gradient taken from a preset gets SEED_COLORS of them
MIN_COLORS, MAX_COLORS, SEED_COLORS = 2, 12, 5

# The presets' colors, the least activity to the most in a light theme (heatmap.js reverses them in a dark theme,
# apart from NO_FLIP). Lime, Olive, Ice, Magenta, Flame: the Review Heatmap add-on's themes; Ocean: ColorBrewer
# YlGnBu; Sunset: CARTO Sunset; Viridis: matplotlib; Rainbow: Google Turbo without its darkest ends.
PRESET_COLORS = {
    "lime": ["#d6e685", "#bddb7a", "#a4d06f", "#8cc665", "#74ba58", "#5cae4c", "#44a340", "#378f36", "#2a7b2c", "#1e6823"],
    "olive": ["#dae289", "#bbd179", "#9cc069", "#8ab45d", "#78a851", "#669d45", "#648b3f", "#637939", "#4f6e30", "#3b6427"],
    "ice": ["#a8d5f6", "#95c8f3", "#82bbf0", "#70afee", "#5da2eb", "#4a95e8", "#3889e6", "#257ce3", "#126fe0", "#0063de"],
    "magenta": ["#fde0dd", "#fcc5c0", "#fa9fb5", "#f768a1", "#ea4e9c", "#dd3497", "#ae017e", "#7a0177", "#610070", "#49006a"],
    "flame": ["#ffeda0", "#fed976", "#feb24c", "#fd8d3c", "#fc6d33", "#fc4e2a", "#e31a1c", "#d00d21", "#bd0026", "#800026"],
    "rainbow": ["#4145ab", "#4675ed", "#39a2fc", "#1bcfd4", "#24eca6", "#61fc6c", "#a4fc3b", "#d1e834", "#f3c63a",
                "#fe9b2d", "#f36315", "#d93806"],
    "ocean": ["#edf8b1", "#c7e9b4", "#7fcdbb", "#41b6c4", "#1d91c0", "#225ea8", "#253494", "#081d58"],
    "sunset": ["#fcde9c", "#faa476", "#f0746e", "#e34f6f", "#dc3977", "#b9257a", "#7c1d6f"],
    "viridis": ["#fde725", "#b5de2b", "#6ece58", "#35b779", "#1f9e89", "#26828e", "#31688e", "#3e4989", "#482878",
                "#440154"],
}
NO_FLIP = ("rainbow",)


def _color_list(cols):
    if not isinstance(cols, (list, tuple)):
        return None
    cols = [c for c in cols if isinstance(c, str) and c]
    return cols[:MAX_COLORS] if len(cols) >= MIN_COLORS else None


def customs_of(conf_get):
    """The saved gradients. Before they could be saved there was one ("custom", Heatmap_Palette_Colors): it is the
    first one while none is saved."""
    saved = conf_get("Heatmap_Custom_Palettes", None)
    out = []
    if isinstance(saved, (list, tuple)):
        for p in saved:
            if not isinstance(p, dict):
                continue
            cols = _color_list(p.get("colors"))
            pid = str(p.get("id") or "")
            if cols and pid and all(o["id"] != pid for o in out):
                out.append({"id": pid, "name": str(p.get("name") or pid), "colors": cols})
    if not out and conf_get("Heatmap_Palette", "") == "custom":
        out.append({"id": "1", "name": "Custom 1",
                    "colors": _color_list(conf_get("Heatmap_Palette_Colors", None)) or list(DEFAULT_COLORS)})
    return out


def palette_of(conf_get, customs=None):
    """The chosen palette's key ("" when it is unknown, or a gradient that was deleted)."""
    value = conf_get("Heatmap_Palette", "")
    if value in KEYS:
        return value
    customs = customs_of(conf_get) if customs is None else customs
    if value == "custom":  # the one gradient of before
        return CUSTOM + customs[0]["id"] if customs else ""
    if isinstance(value, str) and value.startswith(CUSTOM) and any(CUSTOM + p["id"] == value for p in customs):
        return value
    return ""


def colors_of(conf_get):
    """The chosen gradient's colors, or None for a preset (its colors are in heatmap.js)."""
    customs = customs_of(conf_get)
    key = palette_of(conf_get, customs)
    for p in customs:
        if CUSTOM + p["id"] == key:
            return list(p["colors"])
    return None


def new_id(customs):
    used = {p["id"] for p in customs}
    n = 1
    while str(n) in used:
        n += 1
    return str(n)


def _rgb(c):
    c = str(c or "").lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    try:
        v = int(c[:6], 16)
    except ValueError:
        return None
    return (v >> 16 & 255, v >> 8 & 255, v & 255)


def _mix(rgb, other, t):
    return "#%02x%02x%02x" % tuple(round(a + (b - a) * t) for a, b in zip(rgb, other))


def seed_colors(key, customs, base_color=None, dark=False):
    """A new gradient's colors: those of the palette shown (a gradient's own, a preset's spread over SEED_COLORS (5), in the
    order a dark theme shows them), or with the chosen color, its light to dark shades."""
    for p in customs:
        if CUSTOM + p["id"] == key:
            return list(p["colors"])
    cols = PRESET_COLORS.get(key)
    if cols:
        n = len(cols)
        picked = [cols[round(i * (n - 1) / (SEED_COLORS - 1))] for i in range(SEED_COLORS)]
        return picked[::-1] if dark and key not in NO_FLIP else picked
    rgb = _rgb(base_color)
    if rgb is None:
        return list(DEFAULT_COLORS)
    return [_mix(rgb, (255, 255, 255), 0.72), _mix(rgb, (255, 255, 255), 0.3), _mix(rgb, (0, 0, 0), 0.25)]
