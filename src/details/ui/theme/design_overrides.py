# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Global look of the Deep Dive window (soft pill UI), layered on top of the
base stylesheet so the older rules stay as a fallback."""

from .. import ThemePalettes
from .color_utils import hex_to_rgba


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


def get_design_overrides(is_dark, palette=None):
    c = _colors(is_dark, palette)
    glow = _mix(c["bg"], c["accent"], 0.10 if is_dark else 0.07)
    a = c["accent"]
    tint = lambda col, k: hex_to_rgba(col, k)
    idle = tint(c["muted"], 0.07)
    hover = tint(a, 0.14)
    # Clean surfaces shared with the Deep Dive cards: one step above the
    # window background, with a hairline border.
    if is_dark:
        surface = "rgba(255, 255, 255, 0.035)"
        hairline = "rgba(255, 255, 255, 0.07)"
    else:
        surface = "rgba(255, 255, 255, 0.92)"
        hairline = "rgba(0, 0, 0, 0.08)"
    return f"""
        /* ---- Soft pill UI ---- */
        QDialog {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {glow}, stop:0.3 {c['bg']}, stop:1 {c['bg']});
        }}
        QFrame#toolbar {{
            background: {surface};
            border: 1px solid {hairline};
            border-radius: 16px;
        }}
        QPushButton {{
            background: {idle};
            border: 1px solid {tint(c['muted'], 0.36)};
            border-radius: 10px;
            padding: 7px 16px;
        }}
        QPushButton:hover {{
            background: {hover};
            border-color: {tint(a, 0.7)};
        }}
        QPushButton:pressed {{
            background: {tint(a, 0.30)};
            border-color: {a};
            color: {c['text']};
        }}
        QPushButton.toolbar_btn {{
            border-radius: 9px;
            border: 1px solid {tint(c['muted'], 0.36)};
        }}
        QPushButton.toolbar_btn:hover {{
            background: {hover};
            border: 1px solid {tint(a, 0.7)};
        }}
        QPushButton.toolbar_btn:checked, QPushButton.toolbar_btn:checked:hover {{
            background: {tint(a, 0.20)};
            border: 1px solid {a};
        }}

        QLineEdit.search_bar, QLineEdit#search_bar {{
            background: {idle};
            border: 1px solid {tint(c['muted'], 0.36)};
            border-radius: 12px;
        }}
        QLineEdit.search_bar:focus, QLineEdit#search_bar:focus {{
            background: {tint(a, 0.08)};
            border: 1px solid {a};
        }}

        /* Tabs as a segmented pill row */
        QTabWidget::pane {{
            border: none;
            margin-top: 0px;
        }}
        QTabBar::tab {{
            background: transparent;
            color: {c['muted']};
            border: none;
            border-radius: 10px;
            padding: 7px 16px;
            margin: 4px 3px 6px 3px;
            font-weight: 600;
            font-size: 13px;
        }}
        QTabBar::tab:hover {{
            background: {tint(c['muted'], 0.12)};
            color: {c['text']};
            border: none;
        }}
        QTabBar::tab:selected {{
            background: {tint(a, 0.20)};
            color: {c['text']};
            border: none;
        }}
        QTabBar::tab:selected:hover {{
            background: {tint(a, 0.26)};
        }}
        QTabBar QToolButton {{
            border: none;
            border-radius: 8px;
            background: {idle};
        }}

        /* Deep Dive title */
        QLabel#expanded_title {{
            font-size: 17px;
            font-weight: 800;
            letter-spacing: 0px;
            color: {c['text']};
        }}
        /* Table pane as a card */
        QTabWidget::pane {{
            background: {surface};
            border: 1px solid {hairline};
            border-radius: 16px;
        }}
        /* Table */
        QTableWidget {{ background: transparent; alternate-background-color: {tint(c['muted'], 0.07)}; }}
        QHeaderView::section {{ background: transparent; }}
        QTableWidget QTableCornerButton::section {{ background: transparent; }}
        QTableWidget::item {{
            padding: 5px 10px;
            border-bottom: 1px solid {tint(c['border'], 0.55)};
        }}
        QTableWidget::item:hover {{
            background: {tint(c['muted'], 0.07)};
        }}
        QTableWidget::item:selected {{
            background: {tint(a, 0.22)};
            border-bottom: 1px solid {tint(c['border'], 0.55)};
        }}
        QHeaderView::section {{
            padding: 10px 10px;
            border-bottom: 1px solid {tint(c['border_strong'], 0.8)};
            font-size: 10px;
            letter-spacing: 1px;
        }}

        /* Scrollbars: thinner, no outline */
        QScrollBar:vertical {{ width: 6px; margin: 2px 0; }}
        QScrollBar:horizontal {{ height: 6px; margin: 0 2px; }}
        QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
            border: none;
            border-radius: 3px;
        }}
        QScrollBar::handle:vertical {{ margin: 0; min-height: 36px; }}
        QScrollBar::handle:horizontal {{ margin: 0; min-width: 36px; }}

        QListWidget {{
            border-radius: 12px;
            border: 1px solid {tint(c['border_strong'], 0.7)};
        }}
        QListWidget::item {{ border-radius: 8px; }}
        QListWidget::item:selected {{
            background: {tint(a, 0.20)};
            border: none;
        }}
        QGroupBox {{
            border: 1px solid {tint(c['border'], 0.8)};
            border-radius: 12px;
        }}
    """
