# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QHBoxLayout, QLabel, QPainter, QSize, QWidget, Qt


class ElidedTitleLabel(QLabel):
    """Chart title that gives way (with an ellipsis) when the header gets
    crowded, so the legend toggles next to it are never clipped."""

    # Fraction of its natural width the title may keep when the header is
    # crowded (1.0 = never shrink, plain QLabel behaviour).
    shrink_to = 1.0

    def minimumSizeHint(self):
        base = super().minimumSizeHint()
        if self.shrink_to >= 1.0:
            return base
        # May give up to ~12% of its width (ellipsis) before anything else
        # in the header is squeezed.
        return QSize(max(28, int(self.sizeHint().width() * self.shrink_to)), base.height())

    def paintEvent(self, event):
        text = self.text()
        fm = self.fontMetrics()
        if not text or self.width() >= self.sizeHint().width() - 1:
            if self.toolTip() == text:
                self.setToolTip("")
            return super().paintEvent(event)
        if not self.toolTip():
            self.setToolTip(text)
        p = QPainter(self)
        p.setFont(self.font())
        p.setPen(self.palette().windowText().color())
        p.drawText(
            self.rect(),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            fm.elidedText(text, Qt.TextElideMode.ElideRight, int(self.width() * 0.9)),
        )
        p.end()

from .adaptive_stats_widget import AdaptiveStatsWidget


def resolve_chart_stats_state(config_manager, bottom_stats_key, all_stats_key):
    config = getattr(config_manager, "config", {}) if config_manager is not None else {}
    show_bottom_stats = bool(config.get(bottom_stats_key, False))
    show_all_stats = bool(config.get(all_stats_key, True))
    return {
        "show_bottom_stats": show_bottom_stats,
        "show_all_stats": show_all_stats,
        "show_header_stats": (not show_bottom_stats) and show_all_stats,
    }


def apply_chart_stats_state(chart, config_manager, bottom_stats_key, all_stats_key):
    state = resolve_chart_stats_state(config_manager, bottom_stats_key, all_stats_key)
    state["show_chart_stats"] = state["show_bottom_stats"] and state["show_all_stats"]
    if chart is not None:
        setattr(chart, "show_stats", state["show_chart_stats"])
    if state["show_header_stats"] and chart is not None and hasattr(chart, "get_stats_text"):
        state["stats_text"] = chart.get_stats_text()
    else:
        state["stats_text"] = None
    return state


def create_chart_header(
    parent=None,
    title=None,
    title_object_name=None,
    stats_text=None,
    show_header_stats=False,
    uppercase_title=True,
):
    header = QWidget(parent)
    layout = QHBoxLayout(header)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    if title:
        title_text = str(title or "")
        if uppercase_title:
            title_text = title_text.upper()
        title_label = ElidedTitleLabel(title_text, parent=header)
        if title_object_name:
            title_label.setObjectName(title_object_name)
        layout.addWidget(title_label)

    stats_widget = None
    if show_header_stats and stats_text is not None:
        stats_widget = AdaptiveStatsWidget(stats_text, parent=header)
        layout.addWidget(stats_widget)

    layout.addStretch()
    return header, layout, stats_widget


def create_chart_header_for_chart(
    chart,
    config_manager,
    bottom_stats_key,
    all_stats_key,
    *,
    parent=None,
    title=None,
    title_object_name=None,
    uppercase_title=True,
    stats_chart=None,
    include_when_no_header_stats=True,
):
    stats_state = apply_chart_stats_state(
        chart,
        config_manager,
        bottom_stats_key,
        all_stats_key,
    )
    if not stats_state["show_header_stats"] and not include_when_no_header_stats:
        return None, None, None, stats_state

    active_stats_chart = stats_chart if stats_chart is not None else chart
    stats_text = None
    if (
        stats_state["show_header_stats"]
        and active_stats_chart is not None
        and hasattr(active_stats_chart, "get_stats_text")
    ):
        stats_text = active_stats_chart.get_stats_text()

    header, layout, stats_widget = create_chart_header(
        parent=parent,
        title=title,
        title_object_name=title_object_name,
        stats_text=stats_text,
        show_header_stats=stats_state["show_header_stats"],
        uppercase_title=uppercase_title,
    )
    return header, layout, stats_widget, stats_state


def refresh_chart_header_stats(container, chart):
    if not (container and chart and hasattr(chart, "get_stats_text")):
        return False

    stats_widget = container.findChild(AdaptiveStatsWidget)
    if stats_widget is None:
        return False

    stats_widget.update_text(chart.get_stats_text())
    return True


def refresh_parent_chart_header_stats(chart):
    if chart is None or not hasattr(chart, "parentWidget"):
        return False
    return refresh_chart_header_stats(chart.parentWidget(), chart)


def connect_chart_header_refresh(
    zoom_source,
    container,
    *,
    enabled=True,
    chart=None,
    chart_getter=None,
):
    if not enabled or zoom_source is None or container is None:
        return False

    zoom_changed = getattr(zoom_source, "zoom_changed", None)
    if zoom_changed is None:
        return False

    if chart_getter is None:
        target_chart = chart if chart is not None else zoom_source
        chart_getter = lambda: target_chart

    zoom_changed.connect(lambda _z, _s, _e: refresh_chart_header_stats(container, chart_getter()))
    return True
