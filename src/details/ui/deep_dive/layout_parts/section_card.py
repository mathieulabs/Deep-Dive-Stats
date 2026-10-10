# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Deep Dive section-card wrapper helpers."""

from aqt.qt import QLayout, QPushButton, QSize, QSizePolicy, Qt, QVBoxLayout, QWidget

from ... import Config
from ....widgets.common import create_hbox_container
from ....widgets.common.chart_header import ElidedTitleLabel
from ....widgets.pinned.widget_factory.styler import apply_style
from ....widgets.pinned.widget_factory.wrapper import ResizableWrapper


def _create_section_header_widget(parent):
    return create_hbox_container(
        parent,
        margins=(0, 0, 0, 0),
        spacing=0,
        alignment=Qt.AlignmentFlag.AlignVCenter,
    )


def _wrap_section_header_controls(dialog, header_layout):
    controls_wrapper, controls_lay = create_hbox_container(
        dialog,
        margins=(0, 0, 0, 0),
        spacing=10,
        alignment=Qt.AlignmentFlag.AlignVCenter,
        object_name="header_controls_wrapper",
    )
    if isinstance(header_layout, QLayout):
        parent_w = header_layout.parentWidget()
        if parent_w:
            controls_lay.addWidget(parent_w)
        else:
            wrapper = QWidget(dialog)
            wrapper.setLayout(header_layout)
            controls_lay.addWidget(wrapper)
    else:
        controls_lay.addWidget(header_layout)
    return controls_wrapper


def _create_section_title_label(parent, label_text, toggle_callback):
    label = ElidedTitleLabel(label_text.upper(), parent=parent)
    label.shrink_to = 0.88
    label.setObjectName("pinned_header")
    label.setCursor(Qt.CursorShape.PointingHandCursor)
    label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

    def on_label_click(event):
        if event.button() == Qt.MouseButton.LeftButton:
            toggle_callback()

    label.mousePressEvent = on_label_click
    return label


def add_section_card(self, label_text, widget_or_layout, spacing=25, target_layout=None, manual_add=False, header_layout=None, state_key=None):
    """Wrap a widget or layout in a themed section card container."""

    if self.grid_mode:
        wid = state_key if state_key else (label_text.lower() if label_text else "unknown_widget")
        col_span = int(self._get_dd_widget_setting(wid, "col_span", 1))
        saved_h = self._get_dd_widget_setting(wid, "height")
        if saved_h is not None:
            saved_h = int(saved_h)
        
        container = ResizableWrapper(
            widget_id=wid, 
            saved_w=None, 
            saved_h=saved_h, 
            resizable=True,
            resize_directions=["r", "b"],
            save_callback=lambda resizable_wrapper, w, h, wid=wid: self._persist_grid_row_height(resizable_wrapper, h),
            parent=self.dialog,
            col_span=col_span
        )
        container.is_deep_dive = True # Allow identifying Deep Dive context in wrapper.py
        container.setProperty("deepdivestats_theme_context", "details")
        container.setProperty("deepdivestats_ignore_forced_dark_theme", False)
        container.height_changed.connect(lambda h, w=container: self._sync_grid_row_height(w, h))
        container.col_span_changed.connect(lambda s, k=wid: self._update_dd_widget_setting(k, "col_span", s))
        container.setObjectName("pinned_widget_card")
        
        container.setCursor(Qt.CursorShape.ArrowCursor)
        
        layer = QVBoxLayout(container)
        top_m = 6 if (header_layout or label_text) else 2
        layer.setContentsMargins(8, top_m, 10, 6)
        layer.setSpacing(2)
        
        local_settings = self.addon_config.config.get(Config.DEEP_DIVE_WIDGET_SETTINGS, {}).get(wid, {})
        global_style = self.addon_config.config.get(Config.DEEP_DIVE_GRID_STYLE, {})
        use_custom = local_settings.get("use_custom_style", False)
        composite_config = self.addon_config.config.copy()
        
        if use_custom:
            composite_config.update(local_settings)
        else:
            composite_config.update(global_style)
            mapping = [
                (Config.PINNED_GLASS, [Config.HEATMAP_SHOW_GLASS, Config.FACECARDS_SHOW_GLASS]),
                (Config.PINNED_GLASS_INTENSITY, [Config.HEATMAP_GLASS_INTENSITY, Config.FACECARDS_GLASS_INTENSITY]),
                (Config.PINNED_GLASS_BLUR, [Config.HEATMAP_GLASS_BLUR, Config.FACECARDS_GLASS_BLUR]),
                (Config.PINNED_GLASS_BORDER, [Config.HEATMAP_GLASS_BORDER, Config.FACECARDS_GLASS_BORDER])
            ]
            for generic, specifics in mapping:
                if generic in global_style:
                    for specific in specifics:
                        composite_config[specific] = global_style[generic]
        
        class DummyConfigManager:
            def __init__(self, c): self.config = c
        
        apply_style(container, config_manager=DummyConfigManager(composite_config))
        
        from ..context_menu import DeepDiveContextMenu
        context_menu = DeepDiveContextMenu(self)
        section_key = state_key if state_key else (label_text.strip().lower() if label_text else "unknown")
        
        container.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        container.customContextMenuRequested.connect(
            lambda pos, w=container, k=section_key: context_menu.show(w, k, pos)
        )
        
        show_bottom_stats = self.addon_config.config.get(Config.DEEP_DIVE_SHOW_BOTTOM_STATS, False)
        show_all_stats = self.addon_config.config.get(Config.DEEP_DIVE_SHOW_STATS, True)
        
        collapsible = bool(self.addon_config.config.get(Config.DEEP_DIVE_CHARTS_COLLAPSIBLE, True))
        # With the option off every chart stays open, whatever was folded before.
        is_collapsed = bool(self.section_collapse_states.get(section_key, False)) and collapsible

        container.is_collapsed = is_collapsed
        container.state_key = section_key
        
        def toggle_grid_row():
            if not collapsible:
                return
            if not hasattr(self, 'current_grid_layout') or not self.current_grid_layout:
                return
            
            layout = self.current_grid_layout
            idx = -1
            for i in range(layout.count()):
                if layout.itemAt(i).widget() == container:
                    idx = i
                    break
            if idx < 0: return
            
            num_cols = layout.current_cols
            if num_cols <= 0: return
            
            row_idx = idx // num_cols
            start_i = row_idx * num_cols
            end_i = start_i + num_cols
            
            new_state = not getattr(container, "is_collapsed", False)
            for i in range(start_i, min(end_i, layout.count())):
                w = layout.itemAt(i).widget()
                if w: self._update_grid_widget_collapse(w, new_state)
            
            layout.invalidate()
            if layout.parentWidget():
                layout.parentWidget().updateGeometry()
        
        if label_text or header_layout:
            header_widget, header_lay = _create_section_header_widget(container)
            
            btn_toggle = QPushButton("", parent=container)
            btn_toggle.setIconSize(QSize(16, 16))
            btn_toggle.setFixedSize(18, 24)
            btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_toggle.clicked.connect(toggle_grid_row)
            btn_toggle.setVisible(collapsible)
            header_lay.addWidget(btn_toggle)
            container.btn_toggle = btn_toggle

            if label_text:
                label = _create_section_title_label(container, label_text, toggle_grid_row)
                header_lay.addWidget(label)
                header_lay.addSpacing(4)
                container.title_label = label
                
            if header_layout:
                controls_wrapper = _wrap_section_header_controls(self.dialog, header_layout)
                header_lay.addWidget(controls_wrapper)
                container.controls_wrapper = controls_wrapper
                controls_wrapper.setVisible(not is_collapsed)
            else:
                header_lay.addStretch()
                
            layer.addWidget(header_widget)
            container.header_widget = header_widget
            self._apply_grid_header_theme(container)
        if isinstance(widget_or_layout, QLayout):
            layer.addLayout(widget_or_layout)
            # body_widget can't be set for a bare layout unless it is wrapped in a QWidget,
            # but here it is usually a widget.
        else:
            layer.addWidget(widget_or_layout)
            widget_or_layout.setCursor(Qt.CursorShape.ArrowCursor)
            widget_or_layout.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            container.body_widget = widget_or_layout
            if is_collapsed: widget_or_layout.hide()
        
        min_w = 200 if self.grid_mode else 450; min_h = 200
        
        saved_h = self._get_dd_widget_setting(section_key, "height")
        if saved_h:
            min_h = int(saved_h)
        else:
            if wid == "heatmap": min_h = 40
            elif "card" in (wid or "").lower(): min_w = 220; min_h = 200 if self.grid_mode else 250
            elif "stats" in (wid or "").lower(): min_h = 100
            else: min_h = 200

        
        # Widgets can optionally report their type via inner_widget lookup for better min_h defaults
        # (handled inside ResizableWrapper.apply_size)
        
        from ....widgets.chart_utils.geometry import ChartGeometry
        if section_key in ChartGeometry.STATS_EXTRA_HEIGHT:
            wid = section_key
            if show_bottom_stats and show_all_stats:
                min_h += ChartGeometry.STATS_EXTRA_HEIGHT.get(wid, 70)

        
            
        container.setMinimumWidth(min_w) 
        container.original_min_h = min_h
        self._update_grid_widget_height(container, min_h)
        
        if is_collapsed:
            self._update_grid_widget_collapse(container, True, update_persistence=False)

        if hasattr(widget_or_layout, "set_show_stats"):
            widget_or_layout.set_show_stats(show_bottom_stats and show_all_stats)

        return container

