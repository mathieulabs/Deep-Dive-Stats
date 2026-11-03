# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""What can be added to the main screen (charts, stat cards by group, the text widget), how
a new one is pinned, and the "Add Widget..." entry of the right-click menu."""
from aqt.qt import QAction, QTimer

from ..imports import Config, Period
from ...store.registry import WidgetRegistry
from ......i18n import tr, N_

CHARTS = (
    ("activity", N_("Activity")),
    ("retention", N_("Retention")),
    ("heatmap", N_("Heatmap")),
    ("added", N_("Added")),
    ("distribution", N_("Distribution")),
    ("card_counts", N_("Card Counts")),
    ("hourly", N_("Hourly Breakdown")),
    ("future_due", N_("Future Due")),
    ("review_intervals", N_("Review Intervals")),
    ("stability", N_("Card Stability")),
    ("difficulty", N_("Card Difficulty")),
    ("retrievability", N_("Card Retrievability")),
)

# Config attribute names of the stat cards, by group.
STAT_GROUPS = (
    (N_("Study"), ("DASH_SHOW_TIME", "DASH_SHOW_REVIEWS", "DASH_SHOW_AVG_TIME", "DASH_SHOW_REVIEWS_PER_DAY",
               "DASH_SHOW_TIME_PER_DAY", "DASH_SHOW_BEST_DAY", "DASH_SHOW_AGAIN")),
    (N_("Retention"), ("DASH_SHOW_RET_ALL", "DASH_SHOW_RET_YOUNG", "DASH_SHOW_RET_MAT", "DASH_SHOW_RET_TRUE",
                   "DASH_SHOW_REV_YOUNG", "DASH_SHOW_REV_MATURE")),
    (N_("Streaks"), ("DASH_SHOW_STREAK", "DASH_SHOW_LONGEST_STREAK", "DASH_SHOW_ACTIVE_DAYS", "DASH_SHOW_DAYS_LEARNED")),
    (N_("Cards"), ("DASH_SHOW_CARDS_TOTAL", "DASH_SHOW_CARDS_NEW", "DASH_SHOW_CARDS_LEARNING", "DASH_SHOW_CARDS_YOUNG",
               "DASH_SHOW_CARDS_MATURE", "DASH_SHOW_CARDS_SUSPENDED", "DASH_SHOW_CARDS_BURIED",
               "DASH_SHOW_CARDS_DELETED")),
    (N_("Schedule and memory"), ("DASH_SHOW_DUE_TODAY", "DASH_SHOW_BACKLOG", "DASH_SHOW_LAPSES",
                             "DASH_SHOW_AVG_RETRIEVABILITY", "DASH_SHOW_AVG_STABILITY")),
)


def stat_groups_by_key():
    """(group names in order, {stat config key: group name})."""
    names = [group for group, _ in STAT_GROUPS]
    by_key = {}
    for group, attrs in STAT_GROUPS:
        for attr in attrs:
            key = getattr(Config, attr, None)
            if key is not None:
                by_key[key] = group
    return names, by_key


def default_span(widget_type, stat_key=None):
    """The period a new widget opens on: the past month for a chart (readable daily bars;
    Total is one click away on its label), None for a stat card (it keeps its own default,
    Total) and for a widget without a period."""
    from .card_chips import has_time_span

    if widget_type != "stat_card" and has_time_span({"type": widget_type, "stat_key": stat_key}):
        return Period.MONTH
    return None


class Choice:
    """A widget to add: a chart type, a stat card or a text (with its text)."""

    def __init__(self, widget_type, label, stat_key=None, template=None):
        self.widget_type = widget_type
        self.label = label
        self.stat_key = stat_key
        self.template = template

    @property
    def family(self):
        if self.widget_type == "stat_card":
            return "stat"
        return "text" if self.widget_type == "text_label" else "chart"


def pin_new(manager, choice, after_id=None, fields=None, refresh=True):
    """Pin the choice (after after_id, see WidgetRegistry.add) and return its id."""
    extra = dict(fields or {})
    if choice.widget_type == "text_label":
        extra["template"] = choice.template or ""
    new_id = WidgetRegistry.add(
        choice.widget_type, choice.label, stat_key=choice.stat_key,
        time_span=default_span(choice.widget_type, choice.stat_key), after_id=after_id, **extra,
    )
    manager._last_state = None
    manager._last_widget_set = None
    if refresh:
        manager.refresh()
    return new_id


def _pin(manager, widget_type, label, stat_key=None, after_id=None):
    pin_new(manager, Choice(widget_type, label, stat_key=stat_key), after_id=after_id)


def ask_text_template(manager, parent):
    """The text of a new text widget, from a themed dialog, or None when cancelled."""
    from aqt.qt import QCoreApplication, QDialog, QHBoxLayout, QPushButton, QVBoxLayout
    from aqt.theme import theme_manager
    from .....ui.theme import get_settings_dialog_style
    from .....ui.config.widgets.text_label_editor import TextLabelEditor
    from .....ui.config.shared import clamp_dialog_width
    from .....logic.logger import log_swallowed
    from ......qss import set_qss

    dlg = QDialog(parent)
    dlg.setWindowTitle(tr("Add Text Widget"))
    dlg.setMinimumWidth(500)

    cfg = {}
    try:
        cfg = (manager._config_manager.config or {}) if getattr(manager, "_config_manager", None) else {}
        from ....chart_utils.theme import ThemeContext, get_context_theme_config

        cfg = get_context_theme_config(ThemeContext.PINNED, cfg)
        set_qss(dlg, get_settings_dialog_style(bool(theme_manager.get_night_mode()), cfg))
    except Exception:
        log_swallowed()

    layout = QVBoxLayout(dlg)
    layout.setSpacing(12)
    layout.setContentsMargins(20, 20, 20, 16)

    editor = TextLabelEditor(dlg, theme_config=cfg)
    layout.addWidget(editor)

    btn_row = QHBoxLayout()
    btn_row.addStretch()
    cancel_btn = QPushButton(tr("Cancel"))
    ok_btn = QPushButton(tr("Add"))
    ok_btn.setDefault(True)
    cancel_btn.clicked.connect(dlg.reject)
    ok_btn.clicked.connect(dlg.accept)
    btn_row.addWidget(cancel_btn)
    btn_row.addWidget(ok_btn)
    layout.addLayout(btn_row)

    QCoreApplication.processEvents()
    wanted_w = max(dlg.minimumWidth(), dlg.sizeHint().width() + 24)
    dlg.resize(clamp_dialog_width(wanted_w, min_width=500), dlg.sizeHint().height())

    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return editor.get_template().strip()


def add_widget_actions(menu, manager, icon_fn=None, after_def=None):
    """The "Add Widget..." entry: it opens the widget gallery, and the widget picked goes
    right after the one right clicked (after_def), or in a new box below it when it is of
    another kind (see add_here.add_at)."""
    act = QAction(tr("Add Widget..."), menu)
    if icon_fn is not None:
        act.setIcon(icon_fn("plus"))
    target = None
    if isinstance(after_def, dict) and after_def.get("id"):
        from .drag_move import box_of, family, row_of

        target = {"kind": "after", "id": after_def["id"], "family": family(after_def),
                  "box": box_of(after_def), "row": row_of(after_def)}

    def _open():
        from .add_here import open_gallery_at

        open_gallery_at(manager, target)

    # Opened once the menu has closed (a window opened from inside its loop starts white).
    act.triggered.connect(lambda _=False: QTimer.singleShot(0, _open))
    menu.addAction(act)
    return act
