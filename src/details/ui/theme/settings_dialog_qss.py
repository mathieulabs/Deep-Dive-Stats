# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .. import ThemePalettes
from .color_utils import hex_to_rgba
from .palette import get_theme_palette
from .scrollbar_qss import get_scrollbar_style
from .theme_mode import get_theme_effective_is_dark


# Same accents the Deep Dive window uses in native mode (no hard-coded blue).
_DEFAULT_ACCENT_DARK = ThemePalettes.ANKI_LIKE_PALETTE["accent"]
_DEFAULT_HOVER_DARK = ThemePalettes.ANKI_LIKE_PALETTE["accent_hover"]
_DEFAULT_ACCENT_LIGHT = ThemePalettes.ANKI_LIKE_PALETTE_LIGHT["accent"]
_DEFAULT_HOVER_LIGHT = ThemePalettes.ANKI_LIKE_PALETTE_LIGHT["accent_hover"]


import os

_CHECK_ICON = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "assets", "check.svg").replace("\\", "/")


def get_settings_dialog_style(is_dark, conf=None):
    if conf:
        is_dark = get_theme_effective_is_dark(conf)

    if is_dark:
        bg_root = "#18181b"
        bg_surface = "#27272a"
        bg_input = "#3f3f46"
        border_subtle = "#3f3f46"
        border_strong = "#52525b"
        text_primary = "#f4f4f5"
        text_secondary = "#a1a1aa"
        accent = _DEFAULT_ACCENT_DARK
        accent_hover = _DEFAULT_HOVER_DARK
        group_title = "#e4e4e7"
    else:
        bg_root = "#ffffff"
        bg_surface = "#f4f4f5"
        bg_input = "#ffffff"
        border_subtle = "#e4e4e7"
        border_strong = "#d4d4d8"
        text_primary = "#18181b"
        text_secondary = "#71717a"
        accent = _DEFAULT_ACCENT_LIGHT
        accent_hover = _DEFAULT_HOVER_LIGHT
        group_title = "#27272a"
        bg_input = "#ffffff"

    if conf:
        palette = get_theme_palette(conf)
        if palette is not None:
            bg_root       = palette.get("bg_root",       bg_root)
            bg_surface    = palette.get("bg_surface",    bg_surface)
            bg_input      = palette.get("bg_element",    bg_input)
            border_subtle = palette.get("border_subtle", border_subtle)
            border_strong = palette.get("border_strong", border_strong)
            text_primary  = palette.get("text_primary",  text_primary)
            text_secondary = palette.get("text_secondary", text_secondary)
            accent        = palette.get("accent",        accent)
            accent_hover  = palette.get("accent_hover",  accent_hover)
            group_title   = palette.get("text_primary",  group_title)

    font_family = "Segoe UI, sans-serif"

    return f"""
        QDialog {{
            background-color: {bg_root};
            color: {text_primary};
            font-family: "{font_family}";
            font-size: 13px;
        }}
        QScrollArea {{
            background: transparent;
            border: none;
        }}
        QWidget#scroll_content {{
            background: transparent;
        }}
        
        QLabel {{
            color: {text_primary};
            font-size: 13px;
        }}
        QLabel#theme_info_label {{
            color: {text_secondary};
            font-size: 11px;
            font-style: italic;
        }}

        /* Groups */
        QGroupBox {{
            background-color: {bg_surface};
            border: 1px solid {border_subtle};
            border-radius: 6px;
            margin-top: 20px;
            padding-top: 10px;
            font-size: 11px;
            font-weight: 700;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 0px;
            padding: 0 4px 4px 0;
            color: {accent}; 
            background-color: transparent; 
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        /* Tabs - Minimal & Compact */
        QTabWidget::pane {{
            border: none;
            background: transparent;
            border-top: 1px solid {border_subtle};
            top: -1px; 
        }}
        QTabWidget {{
            background: transparent;
        }}
        QTabBar {{
            alignment: left;
        }}
        QTabBar::tear {{
            image: none;
            width: 0px;
            height: 0px;
            background: transparent;
            border: none;
        }}
        QTabBar QToolButton {{
            background: transparent;
            color: {text_secondary};
            border: 1px solid {border_subtle};
            border-radius: 5px;
            padding: 0px;
            margin: 0px 1px;
        }}
        QTabBar QToolButton:hover {{
            background: {hex_to_rgba(accent, 0.08)};
            border-color: {accent};
            color: {text_primary};
        }}
        QTabBar QToolButton:pressed {{
            background: {hex_to_rgba(accent, 0.12)};
            border-color: {accent};
            color: {text_primary};
        }}
        QTabBar::tab {{
            background: transparent;
            color: {text_secondary};
            padding: 4px 12px;
            margin-right: 2px;
            font-weight: 600;
            border: 1px solid {border_subtle};
            border-bottom: 2px solid transparent;
            margin-bottom: 1px;
            font-size: 12px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            border-bottom-left-radius: 0px;
            border-bottom-right-radius: 0px;
        }}
        QTabBar::tab:first {{
            border-bottom-left-radius: 0px;
        }}
        QTabBar::tab:last {{
            border-bottom-right-radius: 0px;
        }}
        QTabBar::tab:hover {{
            color: {text_primary};
            background: {border_subtle};
            border-color: {border_strong};
        }}
        QTabBar::tab:selected {{
            color: {accent};
            border: 1px solid {accent};
            border-bottom: 2px solid {accent};
            background: {hex_to_rgba(accent, 0.08)};
        }}
        
        /* Buttons */
        QPushButton {{
            background-color: {bg_input};
            color: {text_primary};
            border: 1px solid {border_strong};
            border-radius: 6px;
            padding: 6px 16px;
            font-weight: 600;
            font-size: 12px;
        }}
        QPushButton:hover {{
            background-color: {border_subtle};
            border-color: {text_secondary};
        }}
        QPushButton:pressed {{
            background-color: {accent};
            border-color: {accent};
            color: white;
        }}
        
        /* Input Fields */
        QLineEdit, QSpinBox, QDateEdit, QComboBox {{
            background-color: {bg_input};
            color: {text_primary};
            border: 1px solid {border_strong};
            border-radius: 6px;
            padding: 6px 10px;
            selection-background-color: {accent};
            selection-color: white;
        }}
        QLineEdit:focus, QSpinBox:focus, QDateEdit:focus, QComboBox:focus {{
            border: 1px solid {accent};
            background-color: {bg_input};
        }}
        
        /* SpinBox Specifics */
        QSpinBox::up-button, QSpinBox::down-button {{
            width: 20px;
            border: none;
            background: transparent;
            border-radius: 2px;
            margin: 1px;
        }}
        QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
            background-color: {border_subtle};
        }}
        
        /* ComboBox */
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 20px;
            border-left-width: 0px; 
            border-top-right-radius: 6px;
            border-bottom-right-radius: 6px;
        }}
        QComboBox QAbstractItemView {{
            border: 1px solid {border_strong};
            background-color: {bg_surface};
            selection-background-color: {accent};
            selection-color: white;
            border-radius: 4px;
            outline: 0;
        }}

        /* List Widget */
        QListWidget {{
            background-color: {bg_input};
            border: 1px solid {border_strong};
            border-radius: 8px;
            outline: 0;
        }}
        QListWidget::item {{
            padding: 4px 8px;
            border-radius: 4px;
            margin: 1px 2px;
            color: {text_secondary};
            font-size: 12px;
        }}
        QListWidget::item:selected {{
            background-color: {bg_surface};
            color: {text_primary};
            border: 1px solid {accent};
        }}
        QListWidget::item:hover:!selected {{
            background-color: {bg_surface};
            color: {text_primary};
        }}

        /* Checkbox */
        QCheckBox {{
            color: {text_primary};
            spacing: 8px;
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border-radius: 4px;
            border: 1px solid {border_strong};
            background-color: {bg_input};
        }}
        QCheckBox::indicator:checked {{
            background-color: {accent};
            image: url({_CHECK_ICON});
            border-color: {accent};
        }}
        QCheckBox::indicator:hover {{
            border-color: {text_secondary};
        }}

        /* Slider */
        QSlider {{
            background: transparent;
            min-height: 24px;
            max-height: 24px;
        }}
        QSlider::groove:horizontal {{
            border: none;
            height: 4px;
            background: {border_strong};
            margin: 0;
            border-radius: 2px;
        }}
        QSlider::sub-page:horizontal {{
            background: {accent};
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            background: {accent};
            border: 2px solid {bg_root};
            width: 10px;
            height: 10px;
            min-width: 10px;
            max-width: 10px; 
            min-height: 10px;
            max-height: 10px;
            margin: -7px 0; 
            border-radius: 5px; 
        }}
        QSlider::handle:horizontal:hover {{
            background: {accent_hover};
        }}
        
        {get_scrollbar_style(is_dark, vertical=True)}

        /* ---- Soft pill UI (matches the Deep Dive window) ---- */
        QDialog {{
            background: {bg_root};
        }}
        QGroupBox {{
            background: {hex_to_rgba(bg_surface, 0.75)};
            border: 1px solid {hex_to_rgba(border_subtle, 0.9)};
            border-radius: 14px;
            margin-top: 22px;
            padding-top: 12px;
        }}
        QGroupBox::title {{
            left: 4px;
            color: {text_secondary};
            letter-spacing: 1.2px;
        }}
        QTabWidget::pane {{ border: none; }}
        QTabBar {{ alignment: center; }}
        QTabBar::tab {{
            background: transparent;
            color: {text_secondary};
            border: none;
            border-radius: 10px;
            padding: 6px 16px;
            margin: 4px 3px 6px 3px;
            font-weight: 600;
            font-size: 12px;
        }}
        QTabBar::tab:hover {{
            background: {hex_to_rgba(text_secondary, 0.12)};
            color: {text_primary};
            border: none;
        }}
        QTabBar::tab:selected {{
            background: {hex_to_rgba(accent, 0.22)};
            color: {text_primary};
            border: none;
        }}
        QPushButton {{
            background: {hex_to_rgba(text_secondary, 0.09)};
            border: 1px solid {hex_to_rgba(border_strong, 0.75)};
            border-radius: 10px;
            padding: 7px 18px;
        }}
        QPushButton:hover {{
            background: {hex_to_rgba(accent, 0.16)};
            border-color: {hex_to_rgba(accent, 0.75)};
        }}
        QPushButton:pressed {{
            background: {hex_to_rgba(accent, 0.35)};
            border-color: {accent};
            color: {text_primary};
        }}
        QLineEdit, QSpinBox, QDateEdit, QComboBox {{
            border-radius: 10px;
            background: {hex_to_rgba(text_secondary, 0.07)};
            border: 1px solid {hex_to_rgba(border_strong, 0.75)};
        }}
        QLineEdit:focus, QSpinBox:focus, QDateEdit:focus, QComboBox:focus {{
            border: 1px solid {accent};
            background: {hex_to_rgba(accent, 0.08)};
        }}
        QSpinBox {{ padding: 6px 2px 6px 8px; }}
        QListWidget {{
            border-radius: 12px;
            background: {hex_to_rgba(text_secondary, 0.05)};
            border: 1px solid {hex_to_rgba(border_strong, 0.75)};
        }}
        QListWidget::item {{ border-radius: 8px; }}
        QListWidget::item:selected {{
            background: {hex_to_rgba(accent, 0.22)};
            color: {text_primary};
            border: none;
        }}
        QCheckBox::indicator {{
            width: 17px; height: 17px;
            border-radius: 6px;
            border: 1px solid {hex_to_rgba(border_strong, 0.9)};
            background: {hex_to_rgba(text_secondary, 0.07)};
        }}
        QCheckBox::indicator:checked {{
            background: {accent};
            image: url({_CHECK_ICON});
            border-color: {accent};
        }}
        QPushButton#theme_chip:checked {{
            border: 1px solid {accent};
            color: {accent};
            background: {hex_to_rgba(accent, 0.12)};
            font-weight: 700;
        }}
        QSlider::groove:horizontal {{
            height: 5px;
            border-radius: 2px;
            background: {hex_to_rgba(text_secondary, 0.28)};
        }}
        QSlider::sub-page:horizontal {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {accent}, stop:1 {accent_hover});
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            width: 12px; height: 12px; min-width: 12px; max-width: 12px;
            min-height: 12px; max-height: 12px;
            margin: -7px 0; border-radius: 6px;
            background: {accent};
            border: 2px solid {bg_root};
        }}
    """


