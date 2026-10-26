# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .base import ADAPTIVE_CHART_BINNING, CHART_BINNING_SCALE


class Config:
    INCLUDE_DELETED_CARDS = 'Include_Deleted_Cards'
    DECIMAL_TIME = 'Decimal_Time'
    EXCLUDED_DECKS = 'Excluded_Decks'
    EXCLUDED_DATES = 'Excluded_Dates'
    DECK_COLORS = "Deck_Colors"
    SHOW_FULL_DECK_NAME = "Show_Full_Deck_Name"
    VERSION = 'Config_Version'
    BROWSER_LIFETIME_STATS = 'Browser_Lifetime_Stats'
    SHOW_EMPTY_CHARTS = 'Show_Empty_Charts'
    DETAILS_TABS_DATA = 'detailsTabsData'
    DETAILS_VIEW_MODE = 'detailsViewMode'
    SPARKLINE_PRECISION = 'sparklinePrecision'
    RETENTION_SPARKLINE = 'retentionSparkline'
    SHOW_BUTTONS_DIST_VISUAL = 'Show_Buttons_Dist_Visual'
    RETENTION_VISUAL_ALL = 'Retention_Visual_All'
    RETENTION_VISUAL_YOUNG = 'Retention_Visual_Young'
    RETENTION_VISUAL_MATURE = 'Retention_Visual_Mature'
    GLOBAL_ROW_HEIGHT = 'Global_Row_Height'
    TABLE_ZEBRA = 'Table_Zebra'
    SHOW_ACTIVE_DAYS = 'Show_Active_Days'
    DASH_SHOW_RET_ALL = 'Dash_Show_Ret_All'
    DASH_SHOW_RET_YOUNG = 'Dash_Show_Ret_Young'
    DASH_SHOW_RET_MAT = 'Dash_Show_Ret_Mature'
    DASH_SHOW_ACTIVE_DAYS = 'Dash_Show_Active_Days'
    DASH_SHOW_TIME = 'Dash_Show_Time'
    DASH_SHOW_REVIEWS = 'Dash_Show_Reviews'
    DASH_SHOW_AVG_TIME = 'Dash_Show_Avg_Time'
    DASH_SHOW_STREAK = 'Dash_Show_Streak'
    DASH_SHOW_DAYS_LEARNED = 'Dash_Show_Days_Learned'
    DASH_SHOW_LONGEST_STREAK = 'Dash_Show_Longest_Streak'
    DASH_SHOW_REVIEWS_PER_DAY = 'Dash_Show_Reviews_Per_Day'
    DASH_SHOW_TIME_PER_DAY = 'Dash_Show_Time_Per_Day'
    DASH_SHOW_RET_TRUE = 'Dash_Show_Ret_True'
    DASH_SHOW_REV_YOUNG = 'Dash_Show_Rev_Young'
    DASH_SHOW_REV_MATURE = 'Dash_Show_Rev_Mature'
    DASH_SHOW_AGAIN = 'Dash_Show_Again'
    DASH_SHOW_BEST_DAY = 'Dash_Show_Best_Day'
    DASH_SHOW_CARDS_TOTAL = 'Dash_Show_Cards_Total'
    DASH_SHOW_CARDS_NEW = 'Dash_Show_Cards_New'
    DASH_SHOW_CARDS_LEARNING = 'Dash_Show_Cards_Learning'
    DASH_SHOW_CARDS_YOUNG = 'Dash_Show_Cards_Young'
    DASH_SHOW_CARDS_MATURE = 'Dash_Show_Cards_Mature'
    DASH_SHOW_CARDS_SUSPENDED = 'Dash_Show_Cards_Suspended'
    DASH_SHOW_CARDS_BURIED = 'Dash_Show_Cards_Buried'
    DASH_SHOW_CARDS_DELETED = 'Dash_Show_Cards_Deleted'
    DASH_SHOW_DUE_TODAY = 'Dash_Show_Due_Today'
    DASH_SHOW_BACKLOG = 'Dash_Show_Backlog'
    DASH_SHOW_AVG_RETRIEVABILITY = 'Dash_Show_Avg_Retrievability'
    DASH_SHOW_AVG_STABILITY = 'Dash_Show_Avg_Stability'
    DASH_SHOW_LAPSES = 'Dash_Show_Lapses'
    DEEP_DIVE_SHOW_TIME = 'Deep_Dive_Show_Time'
    DEEP_DIVE_SHOW_REVIEWS = 'Deep_Dive_Show_Reviews'
    DEEP_DIVE_SHOW_AVG_TIME = 'Deep_Dive_Show_Avg_Time'
    DEEP_DIVE_SHOW_RET_ALL = 'Deep_Dive_Show_Ret_All'
    DEEP_DIVE_SHOW_RET_YOUNG = 'Deep_Dive_Show_Ret_Young'
    DEEP_DIVE_SHOW_RET_MAT = 'Deep_Dive_Show_Ret_Mature'
    DEEP_DIVE_SHOW_STREAK = 'Deep_Dive_Show_Streak'
    DEEP_DIVE_SHOW_ACTIVE_DAYS = 'Deep_Dive_Show_Active_Days'
    HIERARCHY_ENABLED = 'Hierarchy_Enabled'
    DEEP_DIVE_GRID_MODE = 'Deep_Dive_Grid_Mode'
    DEEP_DIVE_STATS_COLLAPSED = 'Deep_Dive_Stats_Collapsed'
    DEEP_DIVE_GRID_SETTINGS = 'Deep_Dive_Grid_Settings'
    DEEP_DIVE_SHOW_BOTTOM_STATS = "Deep_Dive_Show_Bottom_Stats"
    DEEP_DIVE_SHOW_STATS = "Deep_Dive_Show_Stats"
    DEEP_DIVE_PINNED_SHOW_BOTTOM_STATS = "Deep_Dive_Pinned_Show_Bottom_Stats"
    DEEP_DIVE_PINNED_SHOW_STATS = "Deep_Dive_Pinned_Show_Stats"
    DEEP_DIVE_GRID_COLUMNS = 'Deep_Dive_Grid_Columns'
    DEEP_DIVE_CHART_ORDER = 'Deep_Dive_Chart_Order'
    DETAILS_LAYOUT_STATE = 'Details_Layout_State'
    DETAILS_TABLE_DRAWER_AUTO_CLOSE = 'Details_Table_Drawer_Auto_Close'
    DETAILS_TABLE_DRAWER_SHORTCUT = 'Details_Table_Drawer_Shortcut'
    DETAILS_TABLE_DRAWER_OPEN = 'Details_Table_Drawer_Open'
    DETAILS_TABLE_DRAWER_SIZES = 'Details_Table_Drawer_Sizes'
    DETAILS_TIME_TAB_INDEX = 'Details_Time_Tab_Index'
    DETAILS_DECK_TAB_INDEX = 'Details_Deck_Tab_Index'
    DETAILS_DEEP_DIVE_IDENTIFIER = 'Details_Deep_Dive_Identifier'
    DETAILS_DEEP_DIVE_TITLE = 'Details_Deep_Dive_Title'
    DETAILS_DEEP_DIVE_PERIOD_RANGE = 'Details_Deep_Dive_Period_Range'
    DETAILS_EXPANDED_DECKS = 'Details_Expanded_Decks'
    DETAILS_EXPANDED_DECKS_SET = 'Details_Expanded_Decks_Set'
    DEEP_DIVE_CHARTS_COLLAPSIBLE = 'Deep_Dive_Charts_Collapsible'
    DEEP_DIVE_FILL_HEIGHT = 'Deep_Dive_Fill_Height'
    SHOW_TOP_TOOLBAR_BUTTON = 'Show_Top_Toolbar_Button'
    TOOLBAR_BUTTON_STYLE = 'Toolbar_Button_Style'
    TOOLBAR_STYLE_LOGO = 'logo'
    TOOLBAR_STYLE_TEXT = 'text'
    TOOLBAR_STYLE_NONE = 'none'
    TOOLBAR_BUTTON_TEXT = 'Toolbar_Button_Text'
    OPEN_SHORTCUT = 'Open_Shortcut'

    SHOW_TRENDS = 'Show_Trends'
    STATS_PRECISION = 'Stats_Precision'
    DETAILS_SIDE_VIEW = 'Details_Side_View'
    PIE_CHART_SEPARATE_SUSPENDED = 'Pie_Chart_Separate_Suspended'
    PIE_CHART_SHOW_DELETED = 'Pie_Chart_Show_Deleted'
    PINNED_WIDGETS = 'Pinned_Widgets'
    PINNED_GLASS = 'Pinned_Glass'
    PINNED_GLASS_INTENSITY = 'Pinned_Glass_Intensity'
    PINNED_GLASS_BLUR = 'Pinned_Glass_Blur'
    PINNED_GLASS_BORDER = 'Pinned_Glass_Border'
    PINNED_HOVER_BORDER = 'Pinned_Hover_Border'
    TEXT_WIDGET_SHOW_GLASS = 'Text_Widget_Show_Glass'
    TEXT_WIDGET_GLASS_INTENSITY = 'Text_Widget_Glass_Intensity'
    TEXT_WIDGET_GLASS_BLUR = 'Text_Widget_Glass_Blur'
    TEXT_WIDGET_GLASS_BORDER = 'Text_Widget_Glass_Border'
    TEXT_WIDGET_HOVER_BORDER = 'Text_Widget_Hover_Border'
    FACECARDS_GLASS = 'Facecards_Glass'
    FACECARDS_GLASS_INTENSITY = 'Facecards_Glass_Intensity'
    FACECARDS_GLASS_BLUR = 'Facecards_Glass_Blur'
    FACECARDS_GLASS_BORDER = 'Facecards_Glass_Border'
    FACECARDS_SHOW_GLASS = 'Facecards_Show_Glass'
    FACECARDS_SCALE = 'Facecards_Scale'
    FACECARDS_TITLE_SIZE = 'Facecards_Title_Size'
    FACECARDS_TITLE_COLOR = 'Facecards_Title_Color'
    FACECARDS_TITLE_SHADOW_INTENSITY = 'Facecards_Title_Shadow_Intensity'
    FACECARDS_STAT_SHADOW_INTENSITY = 'Facecards_Stat_Shadow_Intensity'
    FACECARDS_HOVER_EFFECT = 'Facecards_Hover_Effect'
    FACECARDS_INLINE_STATS = 'Facecards_Inline_Stats'
    DASHBOARD_SCALE = 'Dashboard_Scale'
    DASHBOARD_TITLE_SIZE = 'Dashboard_Title_Size'
    DASHBOARD_TITLE_COLOR = 'Dashboard_Title_Color'
    DASHBOARD_SHOW_GLASS = 'Dashboard_Show_Glass'
    DASHBOARD_GLASS_INTENSITY = 'Dashboard_Glass_Intensity'
    DASHBOARD_GLASS_BLUR = 'Dashboard_Glass_Blur'
    DASHBOARD_GLASS_BORDER = 'Dashboard_Glass_Border'
    DASHBOARD_TITLE_SHADOW_INTENSITY = 'Dashboard_Title_Shadow_Intensity'
    DASHBOARD_STAT_SHADOW_INTENSITY = 'Dashboard_Stat_Shadow_Intensity'
    DASHBOARD_HOVER_EFFECT = 'Dashboard_Hover_Effect'
    DASHBOARD_INLINE_STATS = 'Dashboard_Inline_Stats'
    DASH_STAT_ORDER = 'Dash_Stat_Order'
    DASH_STAT_ROW_NUMS = 'Dash_Stat_Row_Nums'
    DASH_STAT_LABELS = 'Dash_Stat_Labels'
    DASH_STAT_STYLES = 'Dash_Stat_Styles'
    DASH_STAT_COLORS = 'Dash_Stat_Colors'  # {stat key: hex} picked for one Deep Dive stat card
    LOCKED_EFFECTS = 'Locked_Effects'
    # Global Stat Colors
    COLOR_TIME = 'Color_Time'
    COLOR_AVG_TIME = 'Color_Avg_Time'
    COLOR_REVIEWS = 'Color_Reviews'
    COLOR_RETENTION = 'Color_Retention'
    COLOR_MATURE = 'Color_Mature'
    COLOR_STREAK = 'Color_Streak'
    COLOR_ACTIVE_DAYS = 'Color_Active_Days'
    # Activity Breakdown Colors
    COLOR_LEARN = 'Color_Learn'
    COLOR_YOUNG = 'Color_Young'
    COLOR_RELEARN = 'Color_Relearn'
    COLOR_CRAM = 'Color_Cram'
    COLOR_NEW = 'Color_New'
    COLOR_SUSPENDED = 'Color_Suspended'
    COLOR_BURIED = 'Color_Buried'
    # Button Distribution Colors
    COLOR_AGAIN = 'Color_Again'
    COLOR_HARD = 'Color_Hard'
    COLOR_GOOD = 'Color_Good'
    COLOR_EASY = 'Color_Easy'
    # Generic chart bar/line color
    COLOR_BAR = 'Color_Bar'
    # Future Due chart colors
    COLOR_FUTURE_DUE = 'Color_Future_Due'
    COLOR_BACKLOG = 'Color_Backlog'
    # Deleted cards
    COLOR_DELETED = 'Color_Deleted'
    # Difficulty / Retrievability gradient (red to green by default)
    COLOR_GRADIENT_LOW = 'Color_Gradient_Low'
    COLOR_GRADIENT_HIGH = 'Color_Gradient_High'
    HEATMAP_GLASS = 'Heatmap_Glass'
    HEATMAP_SHOW_GLASS = 'Heatmap_Show_Glass'
    HEATMAP_GLASS_INTENSITY = 'Heatmap_Glass_Intensity'
    HEATMAP_GLASS_BLUR = 'Heatmap_Glass_Blur'
    HEATMAP_GLASS_BORDER = 'Heatmap_Glass_Border'
    HEATMAP_HIDE_TITLE = 'Heatmap_Hide_Title'
    HEATMAP_HIDE_LABELS = 'Heatmap_Hide_Labels'
    HEATMAP_SHOW_LEGEND = 'Heatmap_Show_Legend'
    HEATMAP_SCALE = 'Heatmap_Scale'
    HEATMAP_EMPTY_OPACITY = 'Heatmap_Empty_Opacity'
    HEATMAP_FILLED_OPACITY = 'Heatmap_Filled_Opacity'
    HEATMAP_EMPTY_WHITE = 'Heatmap_Empty_White'
    HEATMAP_SHOW_FUTURE = 'Heatmap_Show_Future'
    HEATMAP_COLOR = 'Heatmap_Color'
    HEATMAP_TINTED_FUTURE = 'Heatmap_Tinted_Future'
    HEATMAP_ROUNDED = 'Heatmap_Rounded'
    HEATMAP_MONDAY_FIRST = 'Heatmap_Monday_First'
    HEATMAP_NAV_POS = 'Heatmap_Nav_Pos'
    PINNED_BLOCK_ORDER = 'Pinned_Block_Order'
    HEATMAP_COLOR_LEVELS = 'Heatmap_Color_Levels'
    HEATMAP_VIBRANCE = 'Heatmap_Vibrance'
    HEATMAP_ROUNDING = 'Heatmap_Rounding_Radius'
    HEATMAP_INTENSITY_CURVE = 'Heatmap_Intensity_Curve'
    HEATMAP_MULTI_HUE_INTENSITY = 'Heatmap_Multi_Hue_Intensity'
    HEATMAP_METRIC = 'Heatmap_Metric'
    HEATMAP_INVERT_INTENSITY = 'Heatmap_Invert_Intensity'
    HEATMAP_CLICK_BROWSER = 'Heatmap_Click_Browser'
    HEATMAP_SHOW_365_MODE = 'Heatmap_Show_365_Mode'
    HEATMAP_SHOW_CONTINUOUS_MODE = 'Heatmap_Show_Continuous_Mode'
    HEATMAP_SHOW_YEAR_MODE = 'Heatmap_Show_Year_Mode'
    HEATMAP_TOOLTIP_HIDDEN = 'Heatmap_Tooltip_Hidden'
    PINNED_POSITION_TOP = 'Pinned_Position_Top'
    PINNED_CHARTS_COLLAPSIBLE = 'Pinned_Charts_Collapsible'
    PINNED_MARGIN_SIDE = 'Pinned_Margin_Side'
    PINNED_MARGIN_TOP = 'Pinned_Margin_Top'
    PINNED_MARGIN_BOTTOM = 'Pinned_Margin_Bottom'
    PINNED_POSITION_TOP_DECK = 'Pinned_Position_Top_Deck'
    PINNED_USE_ACTIVE_THEME = 'Pinned_Use_Active_Theme'
    PINNED_USE_SEPARATE_THEME = 'Pinned_Use_Separate_Theme'
    PINNED_THEME_PRESET = 'Pinned_Theme_Preset'
    PINNED_THEME_IS_CUSTOM = 'Pinned_Theme_Is_Custom'
    PINNED_THEME_CUSTOM_COLORS = 'Pinned_Theme_Custom_Colors'
    PINNED_THEME_CUSTOM_BASE_MODE = 'Pinned_Theme_Custom_Base_Mode'
    DEEP_DIVE_WIDGET_SETTINGS = 'Deep_Dive_Widget_Settings'
    DEEP_DIVE_GRID_STYLE = 'Deep_Dive_Grid_Style'
    ADAPTIVE_CHART_BINNING = ADAPTIVE_CHART_BINNING
    CHART_BINNING_SCALE = CHART_BINNING_SCALE
    CHART_LINE_OPACITY = 'Chart_Line_Opacity'
    CHART_SHOW_GRID = 'Chart_Show_Grid'
    CHART_BAR_GRADIENT = 'Chart_Bar_Gradient'
    USE_THOUSANDS_SEPARATOR = 'Use_Thousands_Separator'
    ANIMATION_SCOPE = 'Animation_Scope'
    CHART_ANIMATION_VISIBLE_THRESHOLD = 'Chart_Animation_Visible_Threshold'

    # Theme Management
    THEME_PRESET = 'Theme_Preset'
    THEME_IS_CUSTOM = 'Theme_Is_Custom'
    THEME_CUSTOM_COLORS = 'Theme_Custom_Colors'
    THEME_CUSTOM_BASE_MODE = 'Theme_Custom_Base_Mode'
    THEME_CUSTOM_PRESETS = 'Theme_Custom_Presets'

    WEEK_START = 'Week_Start'

    DEFAULT_CONFIG = {
        BROWSER_LIFETIME_STATS: False,
        SHOW_EMPTY_CHARTS: False,
        INCLUDE_DELETED_CARDS: True,
        DECIMAL_TIME: True,
        SPARKLINE_PRECISION: False,
        RETENTION_SPARKLINE: False,
        SHOW_BUTTONS_DIST_VISUAL: True,
        RETENTION_VISUAL_ALL: False,
        RETENTION_VISUAL_YOUNG: False,
        RETENTION_VISUAL_MATURE: False,
        GLOBAL_ROW_HEIGHT: 30,
        TABLE_ZEBRA: True,
        SHOW_FULL_DECK_NAME: True,
        SHOW_ACTIVE_DAYS: True,
        DASH_SHOW_RET_ALL: False,
        DASH_SHOW_RET_YOUNG: True,
        DASH_SHOW_RET_MAT: True,
        DASH_SHOW_ACTIVE_DAYS: True,
        DASH_SHOW_TIME: True,
        DASH_SHOW_REVIEWS: True,
        DASH_SHOW_AVG_TIME: True,
        DASH_SHOW_STREAK: True,
        DASH_SHOW_DAYS_LEARNED: False,
        DASH_SHOW_LONGEST_STREAK: True,
        DASH_SHOW_REVIEWS_PER_DAY: False,
        DASH_SHOW_TIME_PER_DAY: False,
        DASH_SHOW_RET_TRUE: False,
        DASH_SHOW_REV_YOUNG: False,
        DASH_SHOW_REV_MATURE: False,
        DASH_SHOW_AGAIN: False,
        DASH_SHOW_BEST_DAY: False,
        DASH_SHOW_CARDS_TOTAL: False,
        DASH_SHOW_CARDS_NEW: False,
        DASH_SHOW_CARDS_LEARNING: False,
        DASH_SHOW_CARDS_YOUNG: False,
        DASH_SHOW_CARDS_MATURE: False,
        DASH_SHOW_CARDS_SUSPENDED: False,
        DASH_SHOW_CARDS_BURIED: False,
        DASH_SHOW_CARDS_DELETED: False,
        DASH_SHOW_DUE_TODAY: False,
        DASH_SHOW_BACKLOG: False,
        DASH_SHOW_AVG_RETRIEVABILITY: False,
        DASH_SHOW_AVG_STABILITY: False,
        DASH_SHOW_LAPSES: False,
        DEEP_DIVE_SHOW_TIME: True,
        DEEP_DIVE_SHOW_REVIEWS: True,
        DEEP_DIVE_SHOW_AVG_TIME: False,
        DEEP_DIVE_SHOW_RET_ALL: False,
        DEEP_DIVE_SHOW_RET_YOUNG: True,
        DEEP_DIVE_SHOW_RET_MAT: True,
        DEEP_DIVE_SHOW_STREAK: False,
        DEEP_DIVE_SHOW_ACTIVE_DAYS: False,
        HIERARCHY_ENABLED: True,
        DEEP_DIVE_STATS_COLLAPSED: False,
        DEEP_DIVE_SHOW_STATS: False,
        DEEP_DIVE_SHOW_BOTTOM_STATS: True,
        DEEP_DIVE_PINNED_SHOW_BOTTOM_STATS: False,
        DEEP_DIVE_PINNED_SHOW_STATS: True,
        DETAILS_SIDE_VIEW: False,
        SHOW_TRENDS: False,
        STATS_PRECISION: 2,
        PIE_CHART_SEPARATE_SUSPENDED: True,
        PIE_CHART_SHOW_DELETED: False,
        # Default main-screen layout for new profiles: stat cards on top, the
        # heatmap under them (no title), a text line, then the charts.
        PINNED_WIDGETS: [
            {"id": "5eef47a9-d929-4e72-b108-1f54cc335ec9", "type": "stat_card", "label": "Total Time",
             "stat_key": "Dash_Show_Time", "time_span": -1},
            {"id": "eb78cd9a-adb9-4b11-a942-dc7a6b03b8a2", "type": "stat_card", "label": "Reviews",
             "stat_key": "Dash_Show_Reviews", "use_custom_style": False},
            {"id": "0174e131-09c3-48bf-b37a-4ad5a83dca01", "type": "stat_card", "label": "Streak",
             "stat_key": "Dash_Show_Streak"},
            {"id": "ad8c9164-68a5-44b0-b0fc-ded18b86d124", "type": "stat_card", "label": "Active Days",
             "stat_key": "Dash_Show_Active_Days", "time_span": -1},
            {"id": "c31c76a7-345d-4e77-9d0e-13ed3a51618a", "type": "activity", "label": "Activity",
             "stat_key": None, "time_span": 2, "show_time_axis": False, "show_breakdown": True,
             "binning_override": True, "use_custom_style": False, "show_average": True,
             "show_cumulative": True, "chart_opacity": 100},
            {"id": "30380686-e9cd-4ff0-ad28-ef928620bea2", "type": "card_counts", "label": "Card Counts",
             "stat_key": None, "time_span": -1, "separate_suspended": True},
            {"id": "7bece771-5ccf-40bd-a8b3-0b4bb83e14e5", "type": "retention", "label": "Retention",
             "stat_key": None, "time_span": 2, "fit_to_data": True, "visible_series": {"young": True}},
            {"id": "884edd42-06de-44a6-8b06-458ce84b8126", "type": "text_label", "label": "Text Widget",
             "stat_key": None,
             "template": "<span style=\" font-size:11pt;\">Studied {reviews:Today} cards in {total_time:Today} today ({avg_time:Today}/card)</span>",
             "chart_box": 1, "use_custom_style": False, "text_box": 0},
            {"id": "f53b41ab-3c15-4b4b-a0da-f36f1095f077", "type": "heatmap", "label": "Heatmap",
             "stat_key": None, "heatmap_mode": "365", "use_custom_style": False, "chart_box": 1},
        ],
        PINNED_GLASS: True,
        PINNED_GLASS_INTENSITY: 24,
        PINNED_GLASS_BLUR: 0,
        PINNED_GLASS_BORDER: 34,
        PINNED_HOVER_BORDER: True,
        TEXT_WIDGET_SHOW_GLASS: False,
        TEXT_WIDGET_GLASS_INTENSITY: 20,
        TEXT_WIDGET_GLASS_BLUR: 0,
        TEXT_WIDGET_GLASS_BORDER: 50,
        TEXT_WIDGET_HOVER_BORDER: True,
        FACECARDS_GLASS: True,
        FACECARDS_GLASS_INTENSITY: 6,
        FACECARDS_GLASS_BLUR: 0,
        FACECARDS_GLASS_BORDER: 100,
        FACECARDS_SHOW_GLASS: True,
        FACECARDS_SCALE: 75,
        FACECARDS_TITLE_SIZE: 98,
        FACECARDS_TITLE_COLOR: "",
        FACECARDS_TITLE_SHADOW_INTENSITY: 0,
        FACECARDS_STAT_SHADOW_INTENSITY: 0,
        FACECARDS_HOVER_EFFECT: True,
        FACECARDS_INLINE_STATS: False,
        DASHBOARD_SCALE: 100,
        DASHBOARD_TITLE_SIZE: 100,
        DASHBOARD_TITLE_COLOR: "",
        DASHBOARD_SHOW_GLASS: True,
        DASHBOARD_GLASS_INTENSITY: 7,
        DASHBOARD_GLASS_BLUR: 0,
        DASHBOARD_GLASS_BORDER: 100,
        DASHBOARD_TITLE_SHADOW_INTENSITY: 0,
        DASHBOARD_STAT_SHADOW_INTENSITY: 0,
        DASHBOARD_HOVER_EFFECT: True,
        DASHBOARD_INLINE_STATS: False,
        DASH_STAT_ORDER: [
            "Dash_Show_Time", "Dash_Show_Reviews", "Dash_Show_Ret_All", "Dash_Show_Ret_Young",
            "Dash_Show_Ret_Mature", "Dash_Show_Ret_True", "Dash_Show_Avg_Time", "Dash_Show_Streak",
            "Dash_Show_Longest_Streak", "Dash_Show_Days_Learned", "Dash_Show_Active_Days",
            "Dash_Show_Reviews_Per_Day", "Dash_Show_Time_Per_Day", "Dash_Show_Rev_Young", "Dash_Show_Rev_Mature",
            "Dash_Show_Again", "Dash_Show_Best_Day", "Dash_Show_Cards_Total", "Dash_Show_Cards_New",
            "Dash_Show_Cards_Learning", "Dash_Show_Cards_Young", "Dash_Show_Cards_Mature",
            "Dash_Show_Cards_Suspended", "Dash_Show_Cards_Buried", "Dash_Show_Cards_Deleted",
            "Dash_Show_Due_Today", "Dash_Show_Backlog", "Dash_Show_Avg_Retrievability",
            "Dash_Show_Avg_Stability", "Dash_Show_Lapses",
        ],
        DASH_STAT_ROW_NUMS: {},
        DASH_STAT_LABELS: {},
        DASH_STAT_STYLES: {},
        DASH_STAT_COLORS: {},
        LOCKED_EFFECTS: ['Dash_Show_Streak', 'Dash_Show_Active_Days'],
        COLOR_TIME: '#8ab4f8',
        COLOR_AVG_TIME: '#06b6d4',
        COLOR_REVIEWS: '#FF9800',
        COLOR_RETENTION: '#3b82f6',
        COLOR_MATURE: '#4caf50',
        COLOR_STREAK: '#F44336',
        COLOR_ACTIVE_DAYS: '#a78bfa',
        COLOR_LEARN: '#ff9800',
        COLOR_YOUNG: '#8bc34a',
        COLOR_RELEARN: '#f44336',
        COLOR_CRAM: '#9fa8da',
        COLOR_NEW: '#1976d2',
        COLOR_SUSPENDED: '#fdd835',
        COLOR_BURIED: '#9e9e9e',
        HEATMAP_GLASS: False,
        HEATMAP_SHOW_GLASS: False,
        HEATMAP_GLASS_INTENSITY: 43,
        HEATMAP_GLASS_BLUR: 0,
        HEATMAP_GLASS_BORDER: 0,
        HEATMAP_HIDE_TITLE: True,
        HEATMAP_HIDE_LABELS: True,
        HEATMAP_SHOW_LEGEND: True,
        HEATMAP_SCALE: 78,
        HEATMAP_EMPTY_OPACITY: 50,
        HEATMAP_EMPTY_WHITE: False,
        HEATMAP_SHOW_FUTURE: True,
        HEATMAP_FILLED_OPACITY: 100,
        HEATMAP_COLOR: "#3b82f6",
        HEATMAP_COLOR_LEVELS: 20,
        HEATMAP_VIBRANCE: 100,
        HEATMAP_ROUNDING: 30,
        HEATMAP_INTENSITY_CURVE: 100,
        HEATMAP_MULTI_HUE_INTENSITY: False,
        HEATMAP_METRIC: 'reviews',
        HEATMAP_INVERT_INTENSITY: False,
        HEATMAP_CLICK_BROWSER: True,
        HEATMAP_SHOW_365_MODE: True,
        HEATMAP_SHOW_CONTINUOUS_MODE: True,
        HEATMAP_SHOW_YEAR_MODE: True,
        HEATMAP_TOOLTIP_HIDDEN: [],
        PINNED_BLOCK_ORDER: ["stats:0", "charts:1", "texts:0", "charts:0"],
        PINNED_POSITION_TOP: True,
        PINNED_CHARTS_COLLAPSIBLE: False,
        PINNED_MARGIN_SIDE: 20,
        PINNED_MARGIN_TOP: 0,
        PINNED_MARGIN_BOTTOM: 20,
        PINNED_POSITION_TOP_DECK: False,
        PINNED_USE_ACTIVE_THEME: True,
        PINNED_USE_SEPARATE_THEME: False,
        PINNED_THEME_PRESET: "native",
        PINNED_THEME_IS_CUSTOM: False,
        PINNED_THEME_CUSTOM_COLORS: {},
        PINNED_THEME_CUSTOM_BASE_MODE: None,
        HEATMAP_TINTED_FUTURE: False,
        HEATMAP_ROUNDED: False,
        HEATMAP_MONDAY_FIRST: False,
        HEATMAP_NAV_POS: "top_right",
        DEEP_DIVE_GRID_MODE: True,
        DEEP_DIVE_GRID_SETTINGS: {},
        DEEP_DIVE_GRID_COLUMNS: 4,
        DEEP_DIVE_CHART_ORDER: [
            "activity", "retention", "heatmap", "future_due", "distribution",
            "hourly", "card_counts", "review_intervals", "stability",
            "difficulty", "retrievability", "added"
        ],
        DEEP_DIVE_WIDGET_SETTINGS: {
            "heatmap_g": {"heatmap_mode": "365", "col_span": 1},
            "future_due_g": {"time_span_idx": 2, "show_backlog": True},
            "activity_g": {"show_time_axis": True, "col_span": 1, "binning_override": True,
                           "breakdown_enabled": True, "use_custom_style": False, "label": "Activity",
                           "chart_opacity": 100, "show_average": True, "show_cumulative": True},
            "retention_g": {"fit_to_data": True, "binning_override": True, "col_span": 1},
            "review_intervals_g": {"time_span_idx": 3},
            "difficulty_g": {"height": 200},
            "retrievability_g": {"height": 200},
            "added_g": {"height": 200, "col_span": 1},
        },
        DEEP_DIVE_GRID_STYLE: {"Pinned_Glass": True, "Pinned_Glass_Intensity": 20, "Pinned_Glass_Border": 50},
        DETAILS_VIEW_MODE: "deck",
        EXCLUDED_DECKS: [1],
        EXCLUDED_DATES: [],
        THEME_PRESET: "native",
        THEME_IS_CUSTOM: False,
        THEME_CUSTOM_COLORS: {},
        THEME_CUSTOM_BASE_MODE: None,
        THEME_CUSTOM_PRESETS: {},
        ADAPTIVE_CHART_BINNING: True,
        CHART_BINNING_SCALE: 100,
        CHART_LINE_OPACITY: 80,
        CHART_SHOW_GRID: True,
        CHART_BAR_GRADIENT: 43,
        USE_THOUSANDS_SEPARATOR: True,
        ANIMATION_SCOPE: 'all',
        CHART_ANIMATION_VISIBLE_THRESHOLD: 6,
        DETAILS_LAYOUT_STATE: 1,
        DETAILS_TABLE_DRAWER_AUTO_CLOSE: True,
        DETAILS_TABLE_DRAWER_SHORTCUT: 'T',
        DETAILS_TABLE_DRAWER_OPEN: False,
        DETAILS_TABLE_DRAWER_SIZES: [0, 0],
        DETAILS_TIME_TAB_INDEX: 0,
        DETAILS_DECK_TAB_INDEX: 0,
        DETAILS_DEEP_DIVE_IDENTIFIER: None,
        DETAILS_DEEP_DIVE_TITLE: '',
        DETAILS_DEEP_DIVE_PERIOD_RANGE: None,
        DETAILS_EXPANDED_DECKS: [],
        DETAILS_EXPANDED_DECKS_SET: False,
        DEEP_DIVE_CHARTS_COLLAPSIBLE: True,
        DEEP_DIVE_FILL_HEIGHT: True,
        SHOW_TOP_TOOLBAR_BUTTON: True,
        TOOLBAR_BUTTON_STYLE: 'logo',
        TOOLBAR_BUTTON_TEXT: 'Deep Dive',
        OPEN_SHORTCUT: 'Ctrl+Shift+D',
    }
