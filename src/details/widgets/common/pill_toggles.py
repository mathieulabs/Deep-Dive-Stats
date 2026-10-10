# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Header toggles drawn as small pills.

Shared by the Deep Dive cards and the pinned widgets. A checkbox is a pill that
lights up in its own color when on. A radio group looks like a segmented
control where only the selected option is tinted.
"""

from aqt.qt import QColor


def rgba_with_alpha(color, alpha):
    """'rgba(r,g,b,a)' / '#hex' / QColor -> 'rgba(r, g, b, alpha)' (alpha 0-1)."""
    if isinstance(color, str) and color.strip().lower().startswith("rgba("):
        parts = color.strip()[5:-1].split(",")
        q = QColor(int(float(parts[0])), int(float(parts[1])), int(float(parts[2])))
    else:
        q = QColor(color)
    return f"rgba({q.red()}, {q.green()}, {q.blue()}, {float(alpha):.3f})"


def _tokens(text_color, accent, is_dark):
    return {
        "text": rgba_with_alpha(text_color, 1.0),
        "text_off": rgba_with_alpha(text_color, 0.55),
        "tint": rgba_with_alpha(accent, 0.16 if is_dark else 0.12),
        "tint_border": rgba_with_alpha(accent, 0.45),
        "hover": "rgba(255, 255, 255, 0.06)" if is_dark else "rgba(0, 0, 0, 0.05)",
        "hairline": "rgba(255, 255, 255, 0.08)" if is_dark else "rgba(0, 0, 0, 0.10)",
    }


def pill_checkbox_qss(text_color, accent, is_dark, font_weight="600", extra_css=""):
    t = _tokens(text_color, accent, is_dark)
    return f"""
        QCheckBox {{
            color: {t["text_off"]};
            font-weight: {font_weight};
            font-size: 10px;
            spacing: 0px;
            padding: 1px 7px;
            border-radius: 8px;
            border: 1px solid {t["hairline"]};
            background: transparent;
            {extra_css}
        }}
        QCheckBox::indicator {{
            width: 0px; height: 0px;
            border: none;
            background: transparent;
        }}
        QCheckBox:hover {{
            color: {t["text"]};
            background: {t["hover"]};
        }}
        QCheckBox:checked {{
            color: {t["text"]};
            background: {t["tint"]};
            border: 1px solid {t["tint_border"]};
        }}
    """


def pill_radio_qss(text_color, accent, is_dark, extra_css=""):
    t = _tokens(text_color, accent, is_dark)
    return f"""
        QRadioButton {{
            color: {t["text_off"]};
            font-size: 10px;
            font-weight: 600;
            spacing: 0px;
            padding: 1px 7px;
            border-radius: 8px;
            border: 1px solid transparent;
            background: transparent;
            {extra_css}
        }}
        QRadioButton::indicator {{
            width: 0px; height: 0px;
            border: none;
            background: transparent;
        }}
        QRadioButton:hover {{
            color: {t["text"]};
            background: {t["hover"]};
        }}
        QRadioButton:checked {{
            color: {t["text"]};
            background: {t["tint"]};
            border: 1px solid {t["tint_border"]};
        }}
    """
