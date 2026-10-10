# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .. import ThemePalettes
from .palette import get_theme_palette
from .theme_mode import get_theme_base_mode, get_theme_effective_is_dark
from .main_dialog_qss import get_main_dialog_style
from .design_overrides import get_design_overrides
from ....qss import set_qss


def apply_styles(dialog):
    from aqt.qt import QPalette, QColor
    from aqt import mw
    from ...widgets.chart_utils.theme import (
        sync_theme_manager_from_config,
        apply_theme_context,
        theme_already_synced,
        ThemeContext,
    )

    conf = getattr(dialog, "addon_config", None)
    conf_data = conf.config if conf else {}
    is_dark = get_theme_effective_is_dark(conf_data)
    palette = get_theme_palette(conf_data)
    base_mode = get_theme_base_mode(conf_data)

    # Scope-aware flags: only widgets under this dialog should force details mode.
    dialog.setProperty("deepdivestats_force_dark_theme", base_mode == ThemePalettes.MODE_DARK)
    dialog.setProperty("deepdivestats_forced_theme_mode", "" if base_mode == ThemePalettes.MODE_NATIVE else base_mode)
    apply_theme_context(dialog, ThemeContext.DETAILS)
    # Decide before the silent sync below records the new state. apply_styles() runs every time a
    # Deep Dive window is built; if the config and Anki's light/dark mode match what every listener
    # was last synced with, the final broadcast would only restyle everything to the same result, so
    # skip it.
    needs_broadcast = not theme_already_synced(conf_data)
    sync_theme_manager_from_config(conf_data, emit=False)

    set_qss(dialog, get_main_dialog_style(is_dark, palette) + get_design_overrides(is_dark, palette))

    # Painted gradient + glow backdrop instead of a flat window color.
    from .backdrop import install_backdrop
    install_backdrop(dialog, is_dark, palette)

    # With a theme active, override the dialog's QPalette so widgets not covered by
    # QSS (chart containers, table cells, SVG backgrounds) do not show Anki's native
    # palette.
    if palette is not None:
        qpal = QPalette()
        qpal.setColor(QPalette.ColorRole.Window,          QColor(palette["bg_root"]))
        qpal.setColor(QPalette.ColorRole.WindowText,      QColor(palette["text_primary"]))
        qpal.setColor(QPalette.ColorRole.Base,            QColor(palette["bg_surface"]))
        qpal.setColor(QPalette.ColorRole.AlternateBase,   QColor(palette.get("bg_element", palette["bg_surface"])))
        qpal.setColor(QPalette.ColorRole.Text,            QColor(palette["text_primary"]))
        qpal.setColor(QPalette.ColorRole.BrightText,      QColor(palette["text_primary"]))
        qpal.setColor(QPalette.ColorRole.Button,          QColor(palette.get("bg_element", palette["bg_surface"])))
        qpal.setColor(QPalette.ColorRole.ButtonText,      QColor(palette["text_primary"]))
        qpal.setColor(QPalette.ColorRole.Highlight,       QColor(palette["accent"]))
        qpal.setColor(QPalette.ColorRole.HighlightedText, QColor(palette["text_primary"]))
        qpal.setColor(QPalette.ColorRole.Mid,             QColor(palette.get("border_strong", palette["bg_element"] if "bg_element" in palette else palette["bg_surface"])))
        qpal.setColor(QPalette.ColorRole.Dark,            QColor(palette["bg_root"]))
        dialog.setPalette(qpal)
    else:
        if mw:
            dialog.setPalette(mw.palette())

    # Notify live widgets through the unified theme sync path.
    if needs_broadcast:
        sync_theme_manager_from_config(conf_data, emit=True, source="apply_styles")


