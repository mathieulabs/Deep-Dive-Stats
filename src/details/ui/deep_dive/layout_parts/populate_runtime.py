# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Deep Dive layout populate runtime helpers."""


from aqt.qt import QPoint, QRect, QSplitter, Qt, QTimer, QWidget

from ....animations.chart_policy import (
    MIN_VISIBLE_CHART_FRACTION,
    SUPPRESS_CHART_ANIMATIONS_PROPERTY,
    chart_animation_batch,
    collect_chart_animation_targets,
    get_chart_animation_visible_threshold,
)
from ....logic.data.section_fetchers import fetch_section_data
from ....logic.data.transforms.retention_series import build_retention_series
from ... import Config
from .....qss import set_qss
from ....logic.logger import log_error
from ....logic.logger import log_swallowed


def _projected_visible_fraction(widget, viewport):
    if widget is None or viewport is None or not isinstance(widget, QWidget):
        return 0.0
    if widget.width() <= 0 or widget.height() <= 0:
        return 0.0
    try:
        top_left = widget.mapTo(viewport, QPoint(0, 0))
        widget_rect = QRect(top_left, widget.size())
        visible_rect = widget_rect.intersected(viewport.rect())
        visible_area = max(0, int(visible_rect.width())) * max(0, int(visible_rect.height()))
        total_area = max(1, int(widget.width()) * int(widget.height()))
        return max(0.0, min(1.0, float(visible_area) / float(total_area)))
    except Exception:
        return 0.0


def _section_animation_targets(section_widget):
    if section_widget is None or not isinstance(section_widget, QWidget):
        return []
    return collect_chart_animation_targets(section_widget)


def _pending_initial_animation_targets(section_wrappers, viewport):
    targets = []
    seen = set()
    for widget in section_wrappers:
        for chart_target in _section_animation_targets(widget):
            tid = id(chart_target)
            if tid in seen:
                continue
            seen.add(tid)
            if bool(getattr(chart_target, "_initial_animation_done", False)):
                continue
            checker = getattr(chart_target, "_has_meaningful_data_for_animation", None)
            if callable(checker):
                try:
                    if not checker():
                        continue
                except Exception:
                    log_swallowed()
            try:
                if not chart_target.isVisible():
                    continue
            except Exception:
                log_swallowed()
            if _projected_visible_fraction(chart_target, viewport) < MIN_VISIBLE_CHART_FRACTION:
                continue
            targets.append(chart_target)
    return targets

def populate_dashboard(self, grid_container_cls, is_warmup=False):
    """Build the dashboard widgets sequentially to maintain UI responsiveness."""
    pending_defer_reveal = bool(getattr(self, "_defer_deep_dive_chart_reveal", False))

    if not hasattr(self.dialog, 'expanded_scroll') or self.dialog.expanded_scroll is None:
        return

    scroll_bar = self.dialog.expanded_scroll.verticalScrollBar()
    old_scroll = scroll_bar.value()

    if hasattr(self, 'masonry_layout') and self.masonry_layout:
        try:
            while self.masonry_layout.count():
                item = self.masonry_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        except RuntimeError:
            pass # The C++ object was already deleted
        self.masonry_layout = None

    self.dialog.expanded_chart_area.setContentsMargins(0, 0, 0, 0)
    self.dialog.expanded_chart_area.setSpacing(0)
    self._cleanup_previous_view()
    self._defer_deep_dive_chart_reveal = pending_defer_reveal

    self.main_split = QSplitter(Qt.Orientation.Vertical, self.dialog)
    self.main_split.setHandleWidth(9)
    split_border = (
        "rgba(255,255,255,0.1)"
        if self.theme_vars.get("is_dark", False)
        else "rgba(0,0,0,0.08)"
    )
    set_qss(self.main_split,
        f"QSplitter::handle:vertical {{ background: transparent; border-top: 1px solid {split_border}; }}"
    )

    ctx_did = self.last_row_data.get("did") if self.last_row_data else None

    stats_span = self._get_dd_widget_setting("stats", "time_span", self.last_history_range)
    stats_row_data = self.last_row_data
    if stats_span is not None and int(stats_span) != int(self.last_history_range):
         if getattr(self, "_is_skeleton", False):
             stats_row_data = self.last_row_data
         else:
             c_days = self._get_dd_widget_setting("stats", "custom_days", 7)
             stats_row_data = fetch_section_data(
                 self.addon_config,
                 "stats",
                 deck_id=ctx_did,
                 range_type=int(stats_span),
                 custom_days=c_days,
             )

    stats_widget = self._build_stats_section(stats_row_data, manual_add=True, deck_id=ctx_did, time_span=stats_span)
    if stats_widget:
         is_collapsed = self.addon_config.config.get(Config.DEEP_DIVE_STATS_COLLAPSED, False)
         stats_widget.setVisible(not is_collapsed)
         self.dialog.expanded_chart_area.addWidget(stats_widget)
         spacer = QWidget(self.dialog); spacer.setObjectName("stats_spacer")
         spacer.setFixedHeight(15 if not is_collapsed else 0); spacer.setVisible(not is_collapsed)
         self.dialog.expanded_chart_area.addWidget(spacer)

    if self.last_history_data or is_warmup or getattr(self, "_is_skeleton", False):
        suppress_initial_chart_anims_during_build = bool(
            not is_warmup and not getattr(self, "_is_skeleton", False)
        )
        if suppress_initial_chart_anims_during_build:
            try:
                self.dialog.setProperty(SUPPRESS_CHART_ANIMATIONS_PROPERTY, True)
            except Exception:
                log_swallowed()
        from ..responsive_grid import ResponsiveGridLayout
        masonry_container = grid_container_cls(self.dialog, self)
        defer_reveal = bool(
            not is_warmup
            and not getattr(self, "_is_skeleton", False)
            and pending_defer_reveal
        )
        masonry_layout = ResponsiveGridLayout(masonry_container, margin=0, spacing=16)
        masonry_layout.set_preferred_columns(getattr(self, "grid_columns", 3))
        masonry_layout.on_cols_changed = lambda n: QTimer.singleShot(0, self._sync_grid_row_collapse)
        self.current_grid_layout = masonry_layout
        self.masonry_layout = masonry_layout

        masonry_container.setAcceptDrops(True)
        masonry_container.installEventFilter(self._event_filter_proxy)

        self.dialog.expanded_chart_area.addWidget(masonry_container)
        from .fill_height import install as _install_fill_height

        _install_fill_height(self)
        if defer_reveal:
            masonry_container.setVisible(False)

        if not is_warmup:
            self._show_and_animate()

        chart_order = self.addon_config.config.get(Config.DEEP_DIVE_CHART_ORDER, [])

        # Build chart payloads from the latest history at build time, avoiding stale skeleton data when background results arrive mid-queue.
        def _current_activity_payload():
            cur_hist = self._get_widget_history("activity", self.last_history_data)[::-1]
            cur_data = [(h["pretty_date"], h["reviews"]) for h in cur_hist]
            return cur_hist, cur_data

        def _current_retention_payload():
            cur_hist = self._get_widget_history("retention", self.last_history_data)[::-1]
            cur_data = build_retention_series(
                cur_hist,
                count_default=0,
                rate_defaults={"young": 0, "mature": 0},
            )
            return cur_hist, cur_data

        def _build_activity_widget():
            cur_hist, cur_data = _current_activity_payload()
            return self._create_activity_chart_view(cur_data, cur_hist)

        def _build_retention_widget():
            _, cur_data = _current_retention_payload()
            return self._create_retention_chart_view(cur_data)

        widget_builders = [
            (_build_activity_widget, "activity", "Activity"),
            (_build_retention_widget, "retention", "Retention"),
            (lambda: self._build_heatmap_section(self._get_widget_history("heatmap", self.last_history_data), self.last_row_data, self.last_history_range, self.last_history_range, manual_add=True), "heatmap", "Heatmap"),
            (lambda: self._build_future_due_section(self.last_deck_identifier, self.last_history_range, self.last_row_data, manual_add=True), "future_due", "Future Due"),
            (lambda: self._build_distribution_section(self.last_deck_identifier, self._get_dd_widget_setting("distribution", "time_span", self.last_history_range), self.last_row_data, manual_add=True), "distribution", "Answer Buttons"),
            (lambda: self._build_hourly_section(self.last_deck_identifier, self.last_history_range, self.last_row_data, manual_add=True), "hourly", "Hourly Breakdown"),
            (lambda: self._build_card_counts_section(self.last_deck_identifier, self.last_history_range, self.last_row_data, manual_add=True), "card_counts", "Card Counts"),
            (lambda: self._build_review_intervals_section(self.last_deck_identifier, self.last_history_range, self.last_row_data, manual_add=True), "review_intervals", "Review Intervals"),
            (lambda: self._build_stability_section(self.last_deck_identifier, self.last_history_range, self.last_row_data, manual_add=True), "stability", "Stability"),
            (lambda: self._build_difficulty_section(self.last_deck_identifier, self.last_history_range, self.last_row_data, manual_add=True), "difficulty", "Difficulty"),
            (lambda: self._build_retrievability_section(self.last_deck_identifier, self.last_history_range, self.last_row_data, manual_add=True), "retrievability", "Retrievability"),
            (lambda: self._build_added_section(self.last_deck_identifier, self._get_dd_widget_setting("added", "time_span", self.last_history_range), self.last_row_data, manual_add=True), "added", "Added")
        ]

        if chart_order:
            order_map = {name: i for i, name in enumerate(chart_order)}
            widget_builders.sort(key=lambda x: order_map.get(x[1], 999))

        act_header_ref = [None]
        ret_header_ref = [None]
        add_header_ref = [None]

        self._build_queue_active = True

        def process_next_widget():
            if masonry_layout != getattr(self, "current_grid_layout", None):
                if suppress_initial_chart_anims_during_build:
                    try:
                        self.dialog.setProperty(SUPPRESS_CHART_ANIMATIONS_PROPERTY, False)
                    except Exception:
                        log_swallowed()
                return # Stale queue from a previous view
            if not widget_builders:
                self._build_queue_active = False
                _, final_act_data = _current_activity_payload()
                _, final_ret_data = _current_retention_payload()
                self._add_chart_controls(act_header_ref[0], ret_header_ref[0], add_header_ref[0], final_act_data, final_ret_data)

                self._sync_grid_row_collapse()
                if old_scroll > 0:
                    QTimer.singleShot(100, lambda: scroll_bar.setValue(old_scroll))

                self._setup_zoom_sync()
                threshold = get_chart_animation_visible_threshold()
                pending_intro_targets = []
                if defer_reveal:
                    try:
                        masonry_layout.activate()
                    except Exception:
                        log_swallowed()
                    try:
                        self.dialog.expanded_chart_area.activate()
                    except Exception:
                        log_swallowed()
                    try:
                        masonry_container.adjustSize()
                    except Exception:
                        log_swallowed()
                    try:
                        viewport = self.dialog.expanded_scroll.viewport()
                    except Exception:
                        viewport = None
                    # Reveal fully-built real-data charts at once so their native
                    # first showEvent animation runs exactly once, independent of order.
                    masonry_container.setVisible(True)
                    self._defer_deep_dive_chart_reveal = False
                else:
                    try:
                        viewport = self.dialog.expanded_scroll.viewport()
                    except Exception:
                        viewport = None
                try:
                    pending_intro_targets = _pending_initial_animation_targets(
                        list((self.section_wrappers or {}).values()),
                        viewport,
                    )
                except Exception:
                    pending_intro_targets = []
                if suppress_initial_chart_anims_during_build:
                    try:
                        self.dialog.setProperty(SUPPRESS_CHART_ANIMATIONS_PROPERTY, False)
                    except Exception:
                        log_swallowed()
                with chart_animation_batch(
                    self.dialog,
                    pending_intro_targets,
                    threshold=threshold,
                    queue_mode=True,
                    split_large_rows=False,
                ):
                    for chart_target in pending_intro_targets:
                        try:
                            chart_target.maybe_start_initial_animation()
                        except Exception:
                            continue
                if (not is_warmup) and (not getattr(self, "_is_skeleton", False)):
                    self._deep_dive_real_view_shown = True
                return

            builder, k, label = widget_builders.pop(0)
            try:
                res = builder()
                if not res:
                    if not self._build_queue_active: return
                    if is_warmup:
                        QTimer.singleShot(5, process_next_widget)
                    else:
                        process_next_widget()
                    return

                w, h = None, None
                if k == "activity" and isinstance(res, tuple) and len(res) >= 4:
                    w, self.activity_chart, self.stacked_chart, h = res[0:4]
                    act_header_ref[0] = h
                elif k == "retention" and isinstance(res, tuple) and len(res) >= 3:
                    w, self.retention_chart, h = res[0], res[1], res[2]
                    ret_header_ref[0] = h
                    # Seed commit anchor so first _refresh_dashboard_data() can detect deck/span changes
                    if self.retention_chart is not None:
                        self.retention_chart._last_committed_deck_id = self.last_deck_identifier
                elif isinstance(res, tuple):
                    w = res[0]
                    h = res[1] if len(res) > 1 else None
                    if k == "added":
                        self.added_chart = w
                        add_header_ref[0] = h
                    elif k == "distribution":
                        self.dist_chart = w
                    elif k == "heatmap":
                        self.heatmap_chart = w
                    elif k == "hourly":
                        self.hourly_chart = w
                    elif k == "future_due":
                        self.future_due_chart = w
                    elif k == "review_intervals":
                        self.review_intervals_chart = w
                    elif k == "stability":
                        self.stability_chart = w
                    elif k == "difficulty":
                        self.difficulty_chart = w
                    elif k == "retrievability":
                        self.retrievability_chart = w
                else:
                    w = res

                if w:
                    sect = self._add_section_card(label, w, manual_add=True, header_layout=h, state_key=k)
                    if sect:
                        try:
                            masonry_layout.addWidget(sect)
                            self.section_wrappers[k] = sect
                        except RuntimeError:
                            return # Layout deleted or stale
            except RuntimeError as re:
                if "deleted" in str(re): return # UI closed
                log_error(f"RuntimeError building widget {k}: {re}")
            except Exception as e:
                log_error(f"Error building widget {k}: {e}")

            if not self._build_queue_active: return

            if is_warmup:
                QTimer.singleShot(30, process_next_widget)
            else:
                process_next_widget()

        if is_warmup:
            QTimer.singleShot(50, process_next_widget)
        else:
            process_next_widget()



