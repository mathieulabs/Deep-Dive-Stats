# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import (
    QEasingCurve,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPropertyAnimation,
    QPushButton,
    QScrollArea,
    QSize,
    Qt,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import Config
from ..theme.icons import get_svg_icon
from ..theme import apply_styles
from ...animations.motion import animations_enabled
from ...logic.export import setup_export_menu
from ...widgets import RowGroupedStatContainer, StatCardWidget
from ...widgets.stats_cards import (
    DASHBOARD_CARD_SPECS,
    get_dashboard_stat_placeholder_values,
    get_stat_card_info,
    iter_dashboard_stat_cards,
)
from aqt.qt import QSplitter
from ....qss import set_qss


def setup_dashboard_and_overlays(dialog):
        """Setup the dashboard, expanded overlay, and tabs. Export menu is delegated."""
        setup_export_menu(dialog)
        
        dialog.dashboard_frame = QFrame(dialog)
        dialog.dashboard_frame.setObjectName("dashboard_frame")
        
        dialog.stats_container = RowGroupedStatContainer(dialog.dashboard_frame)
        dialog.dashboard_container = QHBoxLayout(dialog.dashboard_frame)
        dialog.dashboard_container.setContentsMargins(8, 8, 8, 6)  # 6px bottom gap before table
        dialog.dashboard_container.addWidget(dialog.stats_container)
        
        set_qss(dialog.dashboard_frame, """
            QFrame#dashboard_frame {
                background-color: transparent;
                border: none;
            }
        """)

        placeholders = get_dashboard_stat_placeholder_values(
            dialog.addon_config.config.get(Config.STATS_PRECISION, 2)
        )
        
        for spec in DASHBOARD_CARD_SPECS:
            title, fallback_color = get_stat_card_info(spec["config_key"])
            card = StatCardWidget(
                title,
                placeholders[spec["field"]],
                "",
                color=fallback_color,
                config_key=spec["config_key"],
                addon_config=dialog.addon_config.config,
                stat_type=spec["stat_type"],
                parent=dialog.stats_container,
            )
            setattr(dialog, spec["attr"], card)
        
        for card in iter_dashboard_stat_cards(dialog):
            dialog.stats_container.add_card(card)
        
        def on_dash_visibility_changed(key, checked):
            dialog.addon_config.set_value(key, checked)
            dialog.update_dashboard_visibility()
                
        dialog.stats_container.set_visibility_callback(on_dash_visibility_changed)

        _order = dialog.addon_config.config.get(Config.DASH_STAT_ORDER, [])
        if isinstance(_order, list):
            _order = [str(key) for key in _order if isinstance(key, str) and key]
        else:
            _order = []
        if _order and Config.DASH_SHOW_AVG_TIME not in _order:
            insert_at = _order.index(Config.DASH_SHOW_RET_MAT) + 1 if Config.DASH_SHOW_RET_MAT in _order else len(_order)
            _order.insert(insert_at, Config.DASH_SHOW_AVG_TIME)
            dialog.addon_config.set_value(Config.DASH_STAT_ORDER, _order)
        # Saved orders from before these cards existed: slot them next to their neighbours.
        for new_key, after_key, before_key in (
            (Config.DASH_SHOW_LONGEST_STREAK, Config.DASH_SHOW_STREAK, None),
            (Config.DASH_SHOW_DAYS_LEARNED, None, Config.DASH_SHOW_ACTIVE_DAYS),
            (Config.DASH_SHOW_RET_TRUE, Config.DASH_SHOW_RET_MAT, None),
        ):
            if _order and new_key not in _order:
                if after_key in _order:
                    _order.insert(_order.index(after_key) + 1, new_key)
                elif before_key in _order:
                    _order.insert(_order.index(before_key), new_key)
                dialog.addon_config.set_value(Config.DASH_STAT_ORDER, _order)
        if _order:
            dialog.stats_container.apply_saved_order(_order)

        _rn = dialog.addon_config.config.get(Config.DASH_STAT_ROW_NUMS, {})
        if _rn:
            dialog.stats_container.set_row_nums(_rn)

        dialog.main_layout.addWidget(dialog.dashboard_frame)
        
        dialog.update_dashboard_visibility()
        
        dialog.expanded_container = QFrame(dialog)
        dialog.expanded_container.setObjectName("expanded_container")
        dialog.expanded_container.setMinimumWidth(300)
        dialog.expanded_container.setVisible(False)
        
        dialog.opacity_effect = QGraphicsOpacityEffect(dialog.expanded_container)
        dialog.expanded_container.setGraphicsEffect(dialog.opacity_effect)
        
        dialog.fade_anim = QPropertyAnimation(dialog.opacity_effect, b"opacity")
        if animations_enabled("details"):
            dialog.fade_anim.setDuration(400)
            dialog.fade_anim.setStartValue(0.0)
        else:
            dialog.fade_anim.setDuration(1)
            dialog.fade_anim.setStartValue(1.0)
        dialog.fade_anim.setEndValue(1.0)
        dialog.fade_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        
        dialog.expanded_layout = QVBoxLayout(dialog.expanded_container)
        dialog.expanded_layout.setContentsMargins(15, 0, 2, 0) # Top margin 0 to align with tab level
        dialog.expanded_layout.setSpacing(0) # Remove gap between header and scroll area
        
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 6)  # small gap above the charts
        
        dialog.expanded_title = QLabel("CHART DETAIL", parent=dialog.expanded_container)
        dialog.expanded_title.setObjectName("expanded_title")
        header_layout.addWidget(dialog.expanded_title, 0, Qt.AlignmentFlag.AlignVCenter)
        
        header_layout.addStretch()
        
        dialog.expanded_header_controls = QHBoxLayout()
        dialog.expanded_header_controls.setObjectName("expanded_header_controls")
        dialog.expanded_header_controls.setContentsMargins(0, 0, 10, 0)
        dialog.expanded_header_controls.setSpacing(8)
        header_layout.addLayout(dialog.expanded_header_controls)
        
        close_btn = QPushButton("", parent=dialog.expanded_container)
        close_btn.setIcon(get_svg_icon("x"))
        close_btn.setIconSize(QSize(16, 16))
        close_btn.setObjectName("expanded_close_btn")
        dialog.expanded_close_btn = close_btn
        close_btn.setProperty("class", "expanded_header_btn")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFlat(True)
        close_btn.clicked.connect(dialog.on_deep_dive_closed)
        header_layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        
        dialog.expanded_layout.addLayout(header_layout)

        dialog.expanded_scroll = QScrollArea(parent=dialog.expanded_container)
        dialog.expanded_scroll.setWidgetResizable(True)
        dialog.expanded_scroll.setObjectName("expanded_scroll")
        dialog.expanded_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        dialog.expanded_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        set_qss(dialog.expanded_scroll, """
            QScrollArea#expanded_scroll { background: transparent; }
            QScrollBar:vertical {
                width: 10px;
                background: transparent;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(128, 128, 128, 0.15);
                min-height: 30px;
                border-radius: 2px;
                margin: 0px 4px 0px 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(128, 128, 128, 0.45);
                border-radius: 4px;
                margin: 0px 2px 0px 2px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        """)
        
        scroll_content = QWidget(dialog.expanded_scroll)
        set_qss(scroll_content, "background: transparent;")
        dialog.expanded_chart_area = QVBoxLayout(scroll_content)
        dialog.expanded_chart_area.setContentsMargins(0, 0, 0, 0)
        dialog.expanded_chart_area.setSpacing(0) # Spacing handled by spacers to prevent hidden-widget jumps
        
        dialog.expanded_stats_layout = None
        
        dialog.expanded_scroll.setWidget(scroll_content)
        dialog.expanded_layout.addWidget(dialog.expanded_scroll)
        
        dialog.layout_splitter = QSplitter(Qt.Orientation.Vertical if not dialog.side_view else Qt.Orientation.Horizontal, parent=dialog)
        dialog.layout_splitter.setHandleWidth(0)  # no divider: the table is a drawer, not a pane
        dialog.layout_splitter.addWidget(dialog.expanded_container)
        dialog.layout_splitter.setCollapsible(0, True) # Allow charts to collapse to 0
        
        dialog.tab_widget = QTabWidget(parent=dialog)
        dialog.tab_widget.setDocumentMode(True)
        dialog.tab_widget.tabBar().setDrawBase(False) # Clean look, no separator line
        dialog.tab_widget.currentChanged.connect(dialog.on_tab_changed)
        
        dialog.layout_splitter.addWidget(dialog.tab_widget)
        dialog.layout_splitter.setCollapsible(1, True) # Allow table/tabs to collapse to 0
        dialog.layout_splitter.setStretchFactor(1, 2)
        dialog.main_layout.addWidget(dialog.layout_splitter, 1)
        from .table_drawer import install as _install_table_drawer

        _install_table_drawer(dialog)
        apply_styles(dialog)
        if hasattr(dialog, "refresh_ui_icons"):
            dialog.refresh_ui_icons()


