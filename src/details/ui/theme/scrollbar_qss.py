# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
def get_scrollbar_style(is_dark, vertical=True):
    orientation = "vertical" if vertical else "horizontal"
    size_prop = "width" if vertical else "height"
    handle_prop = "min-height" if vertical else "min-width"
    
    if is_dark:
        handle_bg = "rgba(255, 255, 255, 0.1)"
        hover_bg = "rgba(255, 255, 255, 0.15)"
        pressed_bg = "rgba(255, 255, 255, 0.2)"
    else:
        handle_bg = "rgba(0, 0, 0, 0.1)"
        hover_bg = "rgba(0, 0, 0, 0.15)"
        pressed_bg = "rgba(0, 0, 0, 0.2)"
        
    margin = "2px 0 2px 0" if vertical else "0 2px 0 2px"
    handle_margin = "0px 2px 0px 2px" if vertical else "2px 0px 2px 0px"

    return f"""
        QScrollBar:{orientation} {{
            background: transparent;
            {size_prop}: 6px;
            margin: {margin};
        }}
        QScrollBar::handle:{orientation} {{
            background: {handle_bg};
            {handle_prop}: 30px;
            border-radius: 4px;
            margin: {handle_margin};
        }}
        QScrollBar::handle:{orientation}:hover {{
            background: {hover_bg};
        }}
        QScrollBar::handle:{orientation}:pressed {{
            background: {pressed_bg};
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
    """
