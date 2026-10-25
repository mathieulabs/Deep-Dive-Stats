# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .. import ThemePalettes
from .color_utils import hex_to_rgba



def get_main_dialog_style(is_dark, palette=None):
    font_family = "Segoe UI, sans-serif"

    if is_dark or palette is not None:
        if not palette:
            # Native dark mode: Anki-like colors
            palette = ThemePalettes.ANKI_LIKE_PALETTE.copy()

        bg_root = palette["bg_root"]
        bg_surface = palette["bg_surface"]
        bg_element = palette["bg_element"]
        border_subtle = palette["border_subtle"]
        border_strong = palette["border_strong"]
        text_primary = palette["text_primary"]
        text_secondary = palette["text_secondary"]
        accent = palette["accent"]
        accent_hover = palette["accent_hover"]
        tab_hover_bg = hex_to_rgba(text_secondary, 0.12)
        tab_selected_bg = hex_to_rgba(accent, 0.12)
        table_sel_bg = hex_to_rgba(accent, 0.24)
        table_sel_text = text_primary
        btn_hover_stop = border_strong
        sb_handle = hex_to_rgba(text_secondary, 0.28 if is_dark else 0.18)
        sb_handle_hover = hex_to_rgba(accent, 0.42 if is_dark else 0.28)
        sb_handle_pressed = hex_to_rgba(accent_hover, 0.58 if is_dark else 0.38)
        sb_handle_border = hex_to_rgba(border_strong, 0.65 if is_dark else 0.75)

        return f"""
            QDialog {{
                background-color: {bg_root};
                color: {text_primary};
                font-family: "{font_family}";
                font-size: 13px;
            }}
            
            /* Dashboard & Toolbar Containers */
            QFrame#dashboard_frame {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 0.03),
                    stop:1 rgba(255, 255, 255, 0.01)
                );
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 12px;
            }}
            
            QFrame#toolbar {{
                background-color: transparent;
                border: none;
            }}
            
            /* Buttons */
            QPushButton {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 {bg_surface},
                    stop:1 {bg_element}
                );
                color: {text_primary};
                border: 1px solid {border_strong};
                border-radius: 8px;
                padding: 7px 15px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 {bg_element},
                    stop:1 {btn_hover_stop}
                );
                border-color: {accent};
                color: {text_primary};
            }}
            QPushButton:pressed {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 {accent},
                    stop:1 {accent_hover}
                );
                border-color: {accent};
                color: white;
                margin: 0px;
            }}
            
            /* Search Input - Modern styling */
            QLineEdit.search_bar, QLineEdit#search_bar {{
                background-color: {hex_to_rgba(bg_surface, 0.4)};
                color: {text_primary};
                border: 1px solid {border_strong};
                border-radius: 10px;
                padding: 6px 36px 6px 12px;
                font-size: 13px;
            }}
            QLineEdit.search_bar:focus, QLineEdit#search_bar:focus {{
                border-color: {accent};
                background-color: {hex_to_rgba(accent, 0.1)};
            }}
            QLineEdit.search_bar::placeholder, QLineEdit#search_bar::placeholder {{
                color: {text_secondary};
            }}

            QPushButton.search_clear_btn {{
                background: transparent;
                border: none;
                border-radius: 9px;
                padding: 0;
            }}
            QPushButton.search_clear_btn:hover {{
                background: {hex_to_rgba(text_secondary, 0.15)};
            }}

            /* Toolbar Buttons - Shared Class */
            QPushButton.toolbar_btn {{
                padding: 2px 10px;
                font-weight: 600;
                font-size: 11px;
                min-height: 24px;
                max-height: 24px;
                border: 1px solid {hex_to_rgba(text_secondary, 0.42)};
            }}
            QPushButton.toolbar_btn:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 {bg_element},
                    stop:1 {border_strong}
                );
                border: 1px solid {accent};
            }}
            QPushButton.toolbar_btn:checked {{
                background-color: {hex_to_rgba(accent, 0.15)};
                border: 1px solid {accent};
            }}
            QPushButton.toolbar_btn:checked:hover {{
                background-color: {hex_to_rgba(accent, 0.15)};
                border: 1px solid {accent};
            }}
            QPushButton.toolbar_btn:pressed {{
                background-color: {hex_to_rgba(accent, 0.25)};
                border: 1px solid {accent};
            }}
            
            /* Tabs */
            QTabWidget::pane {{
                border: none;
                background-color: transparent;
                border-top: 1px solid {border_subtle};
                margin-top: -1px;
            }}
            QTabWidget {{
                background-color: transparent;
            }}
            QTabBar {{
                alignment: center;
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
                border-radius: 6px;
                padding: 1px;
                margin: 0px 1px;
            }}
            QTabBar QToolButton:hover {{
                background: {tab_hover_bg};
                border-color: {accent};
                color: {text_primary};
            }}
            QTabBar QToolButton:pressed {{
                background: {hex_to_rgba(accent, 0.18)};
                border-color: {accent};
                color: {text_primary};
            }}
            QTabBar::tab {{
                background: transparent;
                color: {text_secondary};
                padding: 10px 18px;
                margin-right: 4px;
                font-weight: 600;
                border: 1px solid {border_subtle};
                border-bottom: 3px solid transparent;
                margin-bottom: 0px;
                font-size: 13px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
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
                background: {tab_hover_bg};
                border-color: {border_strong};
            }}
            QTabBar::tab:selected {{
                color: {text_primary};
                border: 1px solid {accent};
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 {tab_selected_bg},
                    stop:1 transparent
                );
                border-bottom: 3px solid {accent};
            }}
            
            /* Table */
            QTableWidget {{
                background-color: {bg_root};
                alternate-background-color: {bg_root};
                color: {text_primary};
                border: none;
                gridline-color: transparent; /* No grid lines */
                selection-background-color: {table_sel_bg};
                selection-color: {table_sel_text};
                outline: none;
            }}
            QTableWidget::item {{
                padding: 4px 8px; /* More roomy */
                border-bottom: 1px solid {border_subtle};
            }}
            QTableWidget::item:selected {{
                background-color: {table_sel_bg};
                border-bottom: 1px solid {border_subtle};
            }}
            
            /* Headers */
            QHeaderView {{
                background-color: transparent;
                border: none;
            }}
            QHeaderView::section {{
                background-color: {bg_root};
                color: {text_secondary};
                text-transform: uppercase;
                font-weight: 700;
                font-size: 10px;
                letter-spacing: 0.8px;
                padding: 8px 8px;
                border: none;
                border-bottom: 1px solid {border_strong};
            }}

            /* Scrollbar */
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 2px 0 2px 0;
            }}
            QScrollBar::handle:vertical {{
                background: {sb_handle};
                border: 1px solid {sb_handle_border};
                min-height: 30px;
                border-radius: 4px;
                margin: 0px 2px 0px 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {sb_handle_hover};
                margin: 0px 1px 0px 1px;
            }}
            QScrollBar::handle:vertical:pressed {{
                background: {sb_handle_pressed};
            }}
            QScrollBar:horizontal {{
                background: transparent;
                height: 8px;
                margin: 0 2px 0 2px;
            }}
            QScrollBar::handle:horizontal {{
                background: {sb_handle};
                border: 1px solid {sb_handle_border};
                min-width: 30px;
                border-radius: 4px;
                margin: 2px 0px 2px 0px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {sb_handle_hover};
                margin: 1px 0px 1px 0px;
            }}
            QScrollBar::handle:horizontal:pressed {{
                background: {sb_handle_pressed};
            }}
            QScrollBar::add-line, QScrollBar::sub-line {{
                background: none;
                border: none;
                height: 0px;
                width: 0px;
            }}
            QScrollBar::add-page, QScrollBar::sub-page {{
                background: none;
            }}
            /* Corner */
            QTableWidget QTableCornerButton::section {{
                background-color: {bg_root};
                border: none;
                border-bottom: 1px solid {border_strong};
            }}

            /* Expanded Overlay */
            QFrame#expanded_container {{
                background-color: transparent;
                border: none;
                border-radius: 0px;
            }}
            QLabel#expanded_title, QLabel#pinned_header {{
                color: {text_secondary};
                font-size: 9px;
                font-weight: 800;
                text-transform: uppercase;
                letter-spacing: 1.2px;
            }}
            /* Shared Header Button Style */
            QPushButton.expanded_header_btn {{
                background: transparent;
                border: none;
                border-radius: 6px;
                padding: 0;
                margin: 0;
            }}
            QPushButton.expanded_header_btn:hover {{
                background: transparent;
            }}
            QPushButton#expanded_close_btn {{
                color: {text_secondary};
            }}
            QPushButton#expanded_close_btn:hover {{
                color: {text_primary};
            }}
            
            /* Splitter - Minimal with Dots */
            QSplitter::handle {{
                background: transparent;
                image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHdpZHRoPSc0JyBoZWlnaHQ9JzE2JyB2aWV3Qm94PScwIDAgNCAxNic+PGNpcmNsZSBjeD0nMicgY3k9JzInIHI9JzEuNScgZmlsbD0nI2ExYTFhYScvPjxjaXJjbGUgY3g9JzInIGN5PSc4JyByPScxLjUnIGZpbGw9JyNhMWExYWEnLz48Y2lyY2xlIGN4PScyJyBjeT0nMTQnIHI9JzEuNScgZmlsbD0nI2ExYTFhYScvPjwvc3ZnPg==);
            }}
            QSplitter::handle:horizontal {{
                width: 8px; /* Small enough but clickable */
                margin: 0; 
            }}
            QSplitter::handle:vertical {{
                height: 8px;
                margin: 0;
            }}

            /* List Widget (for Deck Selector) */
            QListWidget {{
                background-color: {hex_to_rgba(bg_surface, 0.4)};
                border: 1px solid {border_strong};
                border-radius: 10px;
                outline: 0;
            }}
            QListWidget::item {{
                padding: 6px 12px;
                border-radius: 6px;
                margin: 2px 4px;
                color: {text_secondary};
            }}
            QListWidget::item:selected {{
                background-color: {hex_to_rgba(accent, 0.15)};
                color: {text_primary};
                border: 1px solid {accent};
            }}
            QListWidget::item:hover {{
                background-color: {hex_to_rgba(text_secondary, 0.1)};
            }}

            /* GroupBox (optional container) */
            QGroupBox {{
                background-color: transparent;
                border: 1px solid {border_subtle};
                border-radius: 8px;
                margin-top: 12px;
                font-weight: 700;
                color: {text_secondary};
                text-transform: uppercase;
                font-size: 10px;
                letter-spacing: 0.5px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
        """
    else:
        # Native light mode: follow Anki's own light colors
        bg_root = "#ffffff"
        bg_surface = "#f4f4f5"
        border_subtle = "#e4e4e7"
        border_strong = "#d4d4d8"
        text_primary = "#18181b"
        text_secondary = "#71717a"
        accent = "#3b82f6"
        tab_hover_bg = hex_to_rgba(text_primary, 0.05)
        tab_selected_bg = hex_to_rgba(accent, 0.10)
        table_sel_bg = hex_to_rgba(accent, 0.14)
        table_sel_text = text_primary
        sb_handle = hex_to_rgba(text_secondary, 0.22)
        sb_handle_hover = hex_to_rgba(accent, 0.26)
        sb_handle_pressed = hex_to_rgba(accent, 0.36)
        sb_handle_border = hex_to_rgba(border_strong, 0.75)

        return f"""
            QDialog {{
                background-color: {bg_root};
                color: {text_primary};
                font-family: "{font_family}";
                font-size: 13px;
            }}
            
            /* Dashboard & Toolbar Containers - Light Theme */
            QFrame#dashboard_frame {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 1),
                    stop:1 rgba(244, 244, 245, 0.8)
                );
                border: 1px solid {border_subtle};
                border-radius: 12px;
            }}
            
            QFrame#toolbar {{
                background: transparent;
                border: none;
            }}
            
            /* Buttons */
            QPushButton {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 white,
                    stop:1 {bg_surface}
                );
                color: {text_primary};
                border: 1px solid {border_strong};
                border-radius: 8px;
                padding: 7px 15px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 {bg_surface},
                    stop:1 #e4e4e7
                );
                border-color: #a1a1aa;
            }}
            QPushButton:pressed {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 {hex_to_rgba(accent, 0.10)},
                    stop:1 {hex_to_rgba(accent, 0.18)}
                );
                border-color: {accent};
                color: {accent};
            }}

            QPushButton.toolbar_btn {{
                padding: 2px 12px;
                font-weight: 600;
                font-size: 11px;
                min-height: 24px;
                max-height: 24px;
                border: 1px solid {border_strong};
            }}
            QPushButton.toolbar_btn:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 {bg_surface},
                    stop:1 #e4e4e7
                );
                border: 1px solid #a1a1aa;
            }}
            QPushButton.toolbar_btn:checked {{
                background-color: {hex_to_rgba(accent, 0.10)};
                border: 1px solid {accent};
                color: {accent};
            }}
            QPushButton.toolbar_btn:checked:hover {{
                background-color: {hex_to_rgba(accent, 0.10)};
                border: 1px solid {accent};
                color: {accent};
            }}
            QPushButton.toolbar_btn:pressed {{
                background-color: {hex_to_rgba(accent, 0.18)};
                border: 1px solid {accent};
            }}
            
            /* Search Input - Modern styling */
            QLineEdit {{
                background-color: white;
                color: {text_primary};
                border: 1px solid {border_strong};
                border-radius: 8px;
                padding: 7px 12px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {accent};
                background-color: {hex_to_rgba(accent, 0.04)};
            }}

            /* List Widget (for Deck Selector) */
            QListWidget {{
                background-color: white;
                border: 1px solid {border_strong};
                border-radius: 8px;
                outline: 0;
            }}
            QListWidget::item {{
                padding: 6px 12px;
                border-radius: 6px;
                margin: 2px 4px;
                color: {text_secondary};
            }}
            QListWidget::item:selected {{
                background-color: {hex_to_rgba(accent, 0.10)};
                color: {accent};
                border: 1px solid {accent};
            }}
            
            /* Tabs */
            QTabWidget::pane {{
                border: none;
                background: transparent;
                border-top: 2px solid {border_subtle};
                margin-top: -2px;
            }}
            QTabWidget {{
                background: transparent;
            }}
            QTabBar {{
                alignment: center;
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
                border-radius: 6px;
                padding: 1px;
                margin: 0px 1px;
            }}
            QTabBar QToolButton:hover {{
                background: {tab_hover_bg};
                border-color: {accent};
                color: {text_primary};
            }}
            QTabBar QToolButton:pressed {{
                background: {hex_to_rgba(accent, 0.16)};
                border-color: {accent};
                color: {text_primary};
            }}
            QTabBar::tab {{
                background: transparent;
                color: {text_secondary};
                padding: 10px 18px;
                margin-right: 4px;
                font-weight: 600;
                border: 1px solid {border_subtle};
                border-bottom: 3px solid transparent;
                margin-bottom: 0px;
                font-size: 13px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
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
                background: {tab_hover_bg};
                border-color: {border_strong};
            }}
            QTabBar::tab:selected {{
                color: {accent};
                border: 1px solid {accent};
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 {tab_selected_bg},
                    stop:1 transparent
                );
                border-bottom: 3px solid {accent};
            }}
            
            QTableWidget {{
                background-color: {bg_root};
                alternate-background-color: {bg_root}; 
                color: {text_primary};
                border: none;
                gridline-color: transparent;
                selection-background-color: {table_sel_bg};
                selection-color: {table_sel_text};
                outline: none;
            }}
            QTableWidget::item {{
                padding: 4px 8px;
                border-bottom: 1px solid {border_subtle};
            }}
            QTableWidget::item:selected {{
                background-color: {table_sel_bg};
                border-bottom: 1px solid {border_subtle};
            }}
            
            QHeaderView {{
                background-color: transparent;
                border: none;
            }}
            QHeaderView::section {{
                background-color: {bg_root};
                color: {text_secondary};
                text-transform: uppercase;
                font-weight: 600;
                font-size: 10px;
                letter-spacing: 0.6px;
                padding: 8px 8px;
                border: none;
                border-bottom: 2px solid {border_subtle};
            }}

            /* Scrollbar */
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 2px 0 2px 0;
            }}
            QScrollBar::handle:vertical {{
                background: {sb_handle};
                border: 1px solid {sb_handle_border};
                min-height: 30px;
                border-radius: 4px;
                margin: 0px 2px 0px 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {sb_handle_hover};
                margin: 0px 1px 0px 1px;
            }}
            QScrollBar::handle:vertical:pressed {{
                background: {sb_handle_pressed};
            }}
            QScrollBar:horizontal {{
                background: transparent;
                height: 8px;
                margin: 0 2px 0 2px;
            }}
            QScrollBar::handle:horizontal {{
                background: {sb_handle};
                border: 1px solid {sb_handle_border};
                min-width: 30px;
                border-radius: 4px;
                margin: 2px 0px 2px 0px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {sb_handle_hover};
                margin: 1px 0px 1px 0px;
            }}
            QScrollBar::handle:horizontal:pressed {{
                background: {sb_handle_pressed};
            }}
            QScrollBar::add-line, QScrollBar::sub-line {{
                background: none;
                border: none;
                height: 0px;
                width: 0px;
            }}
            QScrollBar::add-page, QScrollBar::sub-page {{
                background: none;
            }}
            QTableWidget QTableCornerButton::section {{
                background-color: {bg_root};
                border: none;
                border-bottom: 2px solid {border_subtle};
            }}

            /* Expanded Overlay */
            QFrame#expanded_container {{
                background-color: transparent;
                border: none;
                border-radius: 0px;
            }}
            QLabel#expanded_title, QLabel#pinned_header {{
                color: {text_secondary};
                font-size: 9px;
                font-weight: 800;
                text-transform: uppercase;
                letter-spacing: 1.2px;
            }}
            /* Shared Header Button Style */
            QPushButton.expanded_header_btn {{
                background: transparent;
                border: none;
                border-radius: 6px;
                padding: 0;
                margin: 0;
            }}
            QPushButton.expanded_header_btn:hover {{
                background: transparent;
            }}
            QPushButton#expanded_close_btn {{
                color: {text_secondary};
            }}
            QPushButton#expanded_close_btn:hover {{
                color: {accent};
            }}
            
            /* Splitter - Minimal with Dots */
            QSplitter::handle {{
                background: transparent;
                image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHdpZHRoPSc0JyBoZWlnaHQ9JzE2JyB2aWV3Qm94PScwIDAgNCAxNic+PGNpcmNsZSBjeD0nIzcxNzE3YScvPjxjaXJjbGUgY3g9JzInIGN5PSc4JyByPScxLjUnIGZpbGw9JyM3MTcxN2EnLz48Y2lyY2xlIGN4PScyJyBjeT0nMTQnIHI9JzEuNScgZmlsbD0nIzcxNzE3YScvPjwvc3ZnPg==);
            }}
            QSplitter::handle:vertical {{
                height: 8px;
                margin: 0;
            }}

            /* GroupBox (optional container) */
            QGroupBox {{
                background-color: transparent;
                border: 1px solid {border_subtle};
                border-radius: 8px;
                margin-top: 12px;
                font-weight: 700;
                color: {text_secondary};
                text-transform: uppercase;
                font-size: 10px;
                letter-spacing: 0.5px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
        """

