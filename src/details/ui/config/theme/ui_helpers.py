# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from ... import ThemePalettes
from .....i18n import tr


def get_builtin_theme_defs():
    return [
        (ThemePalettes.NATIVE, tr("Anki Native")),
        (ThemePalettes.CHARCOAL, "Charcoal"),
        (ThemePalettes.DEEP_OCEAN, "Deep Ocean"),
        (ThemePalettes.NORD, "Nord"),
        (ThemePalettes.GITHUB, "Slate"),
        (ThemePalettes.MIDNIGHT, "Midnight"),
        (ThemePalettes.DARK_PRO, "Dark Pro"),
        (ThemePalettes.DARK_OCEAN, "Dark Ocean"),
        (ThemePalettes.DEFAULT_DARK, "Navy"),
        (ThemePalettes.DARK_PURPLE, "Dark Purple"),
        (ThemePalettes.DRACULA, "Dracula"),
        (ThemePalettes.CATPPUCCIN, "Catppuccin"),
        (ThemePalettes.TOKYO_NIGHT, "Tokyo Night"),
        (ThemePalettes.GRUVBOX, "Gruvbox"),
        (ThemePalettes.MONOKAI, "Monokai"),
        (ThemePalettes.ONE_DARK, "One Dark"),
        (ThemePalettes.AYU_DARK, "Ayu Dark"),
        (ThemePalettes.ROSE_PINE, "Rosé Pine"),
        (ThemePalettes.GRAPHITE, "Graphite"),
        (ThemePalettes.EVERFOREST_DARK, "Everforest Dark"),
        (ThemePalettes.KANAGAWA, "Kanagawa"),
        (ThemePalettes.SOLARIZED_DARK, "Solarized Dark"),
        (ThemePalettes.AURORA, "Aurora"),
        (ThemePalettes.EMBER, "Ember"),
        (ThemePalettes.DEEP_SPACE, "Deep Space"),
        (ThemePalettes.NEON, "Neon"),
        (ThemePalettes.COFFEE, "Coffee"),
        (ThemePalettes.SYNTHWAVE, "Synthwave"),
        (ThemePalettes.ABYSS, "Abyss"),
        (ThemePalettes.BLOOD_MOON, "Blood Moon"),
        (ThemePalettes.TOXIC, "Toxic"),
        (ThemePalettes.STEAMPUNK, "Steampunk"),
        (ThemePalettes.VOID, "Void"),
        (ThemePalettes.VAPORWAVE, "Vaporwave"),
        (ThemePalettes.MATRIX, "Matrix"),
        (ThemePalettes.CYBER_GOLD, "Cyber Gold"),
        (ThemePalettes.AMETHYST, "Amethyst"),
        (ThemePalettes.ABSINTHE, "Absinthe"),
        (ThemePalettes.MODERN_LIGHT, "Modern Light"),
        (ThemePalettes.NATURE_LIGHT, "Nature Light"),
        (ThemePalettes.OCEAN_LIGHT, "Ocean Light"),
        (ThemePalettes.SUNSET_LIGHT, "Sunset Light"),
        (ThemePalettes.LAVENDER, "Lavender"),
        (ThemePalettes.MINT, "Mint"),
        (ThemePalettes.PEACH, "Peach"),
        (ThemePalettes.SOLARIZED, "Solarized"),
        (ThemePalettes.ROSE, "Rose"),
        (ThemePalettes.GRUVBOX_LIGHT, "Gruvbox Light"),
        (ThemePalettes.EVERFOREST_LIGHT, "Everforest Light"),
        (ThemePalettes.PARCHMENT, "Parchment"),
        (ThemePalettes.CHERRY_BLOSSOM, "Cherry Blossom"),
        (ThemePalettes.COTTON_CANDY, "Cotton Candy"),
        (ThemePalettes.DUSK, "Dusk"),
        (ThemePalettes.CORAL, "Coral"),
        (ThemePalettes.LEMON_SORBET, "Lemon Sorbet"),
        (ThemePalettes.GLACIER, "Glacier"),
        (ThemePalettes.CHAMPAGNE, "Champagne"),
    ]


def get_theme_color_keys():
    return [
        ("bg_root", tr("Window Background")),
        ("bg_surface", tr("Surface / Cards")),
        ("bg_element", tr("Element / Button")),
        ("text_primary", tr("Main Text")),
        ("text_secondary", tr("Secondary Text")),
        ("accent", tr("Accent")),
        ("accent_hover", tr("Accent Hover")),
        ("border_strong", tr("Border Strong")),
        ("border_subtle", tr("Border Subtle")),
        ("total_line", tr("Total / Avg")),
    ]


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.hide()
            widget.deleteLater()
        elif child_layout is not None:
            clear_layout(child_layout)


