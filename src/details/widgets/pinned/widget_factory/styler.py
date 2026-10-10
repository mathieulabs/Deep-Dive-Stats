# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QColor
from ....ui import Config
from ...common.color_utils import blend_colors
from .utils import _theme_vars, _addon_config
from .....qss import set_qss
from ...common.surface import dark_surface_rgba

def apply_style(card, base_color=None, config_manager=None, inner_widget=None):
    """Apply the global pinned widget style (glass/shadow) to the card."""
    cfg = config_manager if config_manager else _addon_config()
    
    if hasattr(card, "widget_id") and card.widget_id:
        pinned_widgets = cfg.config.get(Config.PINNED_WIDGETS, [])
        for w_def in pinned_widgets:
            if w_def.get("id") == card.widget_id:
                if w_def.get("use_custom_style", False):
                    composite = cfg.config.copy()
                    composite.update(w_def)
                    class OverrideManager:
                        def __init__(self, c): self.config = c
                    cfg = OverrideManager(composite)
                break

    from ...charts.heatmap import HeatmapWidget
    from ...stats_cards import StatCardWidget
    
    check_targets = [card]
    if inner_widget: check_targets.append(inner_widget)
    
    is_heatmap = any(isinstance(t, HeatmapWidget) or t.findChild(HeatmapWidget) for t in check_targets)
    is_stat = any(isinstance(t, StatCardWidget) or t.findChild(StatCardWidget) for t in check_targets)
    is_text_label = any(str(getattr(t, "wtype", "")) == "text_label" for t in check_targets)
    
    is_facecard = card.objectName() == "StatCard" or is_stat
    # If it's a StatCard, we let its internal style handle some things, but styler handles the container
    
    hover_border = True
    if is_facecard:
        use_glass = cfg.config.get(Config.FACECARDS_SHOW_GLASS, True)
        intensity = cfg.config.get(Config.FACECARDS_GLASS_INTENSITY, 5)
        border_alpha_pct = cfg.config.get(Config.FACECARDS_GLASS_BORDER, 50)
    elif is_text_label:
        use_glass = cfg.config.get(Config.TEXT_WIDGET_SHOW_GLASS, True)
        intensity = cfg.config.get(Config.TEXT_WIDGET_GLASS_INTENSITY, 20)
        border_alpha_pct = cfg.config.get(Config.TEXT_WIDGET_GLASS_BORDER, 50)
        hover_border = cfg.config.get(Config.TEXT_WIDGET_HOVER_BORDER, True)
    elif is_heatmap:
        use_glass = cfg.config.get(Config.HEATMAP_SHOW_GLASS, False)
        intensity = cfg.config.get(Config.HEATMAP_GLASS_INTENSITY, 43)
        border_alpha_pct = cfg.config.get(Config.HEATMAP_GLASS_BORDER, 0)
    else:
        use_glass = cfg.config.get(Config.PINNED_GLASS, True)
        intensity = cfg.config.get(Config.PINNED_GLASS_INTENSITY, 20)
        border_alpha_pct = cfg.config.get(Config.PINNED_GLASS_BORDER, 50)
        hover_border = cfg.config.get(Config.PINNED_HOVER_BORDER, True)
    
    tv = _theme_vars(card)
    if not use_glass:
        card.setGraphicsEffect(None)
        set_qss(card, "background: transparent; border: none;")
        if hasattr(card, "layout") and card.layout():
            card.layout().setContentsMargins(0, 0, 0, 0)
        return
        
    if base_color:
        rgba = QColor(base_color)
        base_rgb = f"{rgba.red()}, {rgba.green()}, {rgba.blue()}"
        border_base = base_rgb
    else:
        # Use theme-derived colors so deep-dive grid cards follow current theme/preset.
        bg_col = QColor(tv.get("bg_hex", "#27272a" if tv['is_dark'] else "#ffffff"))
        border_col = QColor(tv.get("border", "#3f3f46" if tv['is_dark'] else "#d4d4d8"))
        if not bg_col.isValid():
            bg_col = QColor("#27272a" if tv['is_dark'] else "#ffffff")
        if not border_col.isValid():
            border_col = QColor("#3f3f46" if tv['is_dark'] else "#d4d4d8")
        base_rgb = f"{bg_col.red()}, {bg_col.green()}, {bg_col.blue()}"
        border_base = f"{border_col.red()}, {border_col.green()}, {border_col.blue()}"

    if use_glass:
        alpha = intensity / 100.0
        if is_facecard:
            bg_style = f"rgba({base_rgb}, {alpha})"
        else:
            # Soft top-lit glass: slightly denser at the top edge.
            a_top = min(1.0, alpha + 0.06)
            a_bot = max(0.0, alpha - 0.03)
            bg_style = (
                "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
                f"stop:0 rgba({base_rgb}, {a_top:.3f}), stop:1 rgba({base_rgb}, {a_bot:.3f}))"
            )
        
        card.setProperty("blur_radius", 0)
        
        # Keep pinned chart borders readable across themes: the theme border color can
        # be very subtle, so boost its contrast and alpha slightly for non-facecards.
        if not is_facecard:
            border_col = QColor(f"rgb({border_base})")
            # Light mode: darker border; dark mode: lighter border.
            target_col = QColor("#ffffff" if tv['is_dark'] else "#000000")
            if border_col.isValid() and target_col.isValid():
                border_col = blend_colors(border_col, target_col, 0.55)
                border_base = f"{border_col.red()}, {border_col.green()}, {border_col.blue()}"
            border_alpha_pct = min(100, int(round((border_alpha_pct * 1.5) + 12)))

        border_alpha = border_alpha_pct / 100.0
        border_style = f"1px solid rgba({border_base}, {border_alpha})"
        border_hover = f"1px solid rgba({border_base}, {min(1.0, border_alpha + 0.3):.2f})"

        if not is_facecard:
            # Chart cards (Deep Dive and pinned): a flat surface one step lighter than the
            # background and a hairline border. Glass intensity and border settings still
            # drive their strength.
            k = intensity / 100.0
            b = border_alpha_pct / 100.0
            # Hairline unchanged up to 50%, then up to a fully opaque border at 100%.
            def _edge(base_at_half, slope):
                if b <= 0.5:
                    return base_at_half - slope * (0.5 - b)
                return base_at_half + (1.0 - base_at_half) * (((b - 0.5) / 0.5) ** 1.6)
            if tv['is_dark']:
                # Faint veil by default, up to a fully opaque card at 100%.
                surface = dark_surface_rgba(k, tv.get("bg_hex"), lambda x: 0.02 + x * 0.12)
                edge_rgb = "255, 255, 255"
                edge = _edge(0.07, 0.08)
            else:
                surface = f"rgba(255, 255, 255, {min(1.0, 0.8 + k):.3f})"
                edge_rgb = "0, 0, 0"
                edge = _edge(0.08, 0.08)
            bg_style = surface
            border_style = f"1px solid rgba({edge_rgb}, {edge:.3f})"
            border_hover = f"1px solid rgba({edge_rgb}, {min(1.0, edge + 0.10):.3f})"
        
        
        card.setGraphicsEffect(None)
    else:
        bg_style = tv['bg_card']
        border_style = f"1px solid {tv['border']}"
        border_hover = border_style
        card.setGraphicsEffect(None)
        card.setProperty("blur_radius", 0)

    text_color_override = ""
    if is_facecard and use_glass:
        if intensity > 40:
            text_col = "#ffffff" if tv['is_dark'] else "#000000"
            text_color_override = f"color: {text_col} !important;"
            
    if hasattr(card, "layout") and card.layout():
        if use_glass:
            if is_facecard:
                card.layout().setContentsMargins(12, 6, 12, 6)
            else:
                card.layout().setContentsMargins(10, 6, 10, 6)

    set_qss(card, f"""
        QFrame#pinned_widget_card, QFrame#StatCard {{
            background: {bg_style};
            border: {"none" if is_facecard else border_style};
            border-radius: {12 if is_facecard else 14}px;
        }}
        QFrame#pinned_widget_card:hover {{
            border: {"none" if is_facecard else (border_hover if hover_border else border_style)};
        }}
        QLabel#StatCardValue, QLabel#StatCardTitle {{
            {text_color_override}
        }}
        QLabel#pinned_header {{
            background: transparent;
            border: none;
            color: {tv['text_secondary']};
            font-weight: 700;
            font-size: 10px;
            letter-spacing: 0.6px;
            margin-left: 4px;
        }}
    """)




