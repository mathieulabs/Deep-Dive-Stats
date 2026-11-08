# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Which charts Deep Dive shows, and the ones added on demand (charts.more_charts): their
sections, their refresh, adding and removing any chart (right click > Remove, with Undo).

The header button, "Add Chart..." / "Add Stat Card..." of the right-click menus and the
"+ Add Chart" spot open the gallery as the manager of Deep Dive: every chart and stat card,
the ones shown checked, a click adds or removes one, Done applies it all.

The usual charts show until removed (Config.DEEP_DIVE_HIDDEN_CHARTS); the others only once
added (Config.DEEP_DIVE_EXTRA_CHARTS), so the window does not grow for people who do not
want them."""

from aqt.qt import QEvent, QFrame, QLabel, QObject, QPushButton, QRect, QSize, Qt, QTimer, QVBoxLayout

from .. import ADAPTIVE_CHART_BINNING, Config, Period
from ...widgets.charts.daily_metrics import BY_TYPE as DAILY_BY_TYPE, DailyMetricChart
from ...widgets.charts.more_charts import BY_TYPE, CHARTS
from ...widgets.chart_utils.zoom_camera import with_camera
from ...widgets.common import apply_chart_display_config, create_chart_header_for_chart
from ...widgets.common.chart_header import connect_chart_header_refresh, refresh_chart_header_stats
from ..theme.icons import get_svg_icon
from ...logic.logger import log_swallowed
from ....qss import set_qss
from ....i18n import tr

def base_types():
    """The usual Deep Dive charts (the same types as the pinned ones)."""
    from ...widgets.pinned.main_menu.ui.add_widget_menu import CHARTS as BASE

    return [t for t, _label in BASE]


def hidden_types(manager):
    saved = manager.addon_config.config.get(Config.DEEP_DIVE_HIDDEN_CHARTS, []) or []
    return [t for t in saved if t in base_types()]


def extra_types(manager):
    """The added charts, in the order they were added (unknown types left out)."""
    saved = manager.addon_config.config.get(Config.DEEP_DIVE_EXTRA_CHARTS, []) or []
    return [t for t in saved if t in BY_TYPE]


def _days(manager, wtype):
    rows = manager._get_widget_history(wtype, manager.last_history_data) or []
    return list(rows)[::-1]  # oldest first


def _intervals(manager):
    """The review intervals data of the deck shown (the cards as they are now)."""
    if getattr(manager, "_is_skeleton", False):
        return {}
    from ...logic.metrics import ReviewIntervalsDataProvider

    row = getattr(manager, "last_row_data", None) or {}
    return ReviewIntervalsDataProvider.fetch_data(
        manager.addon_config, row.get("did"), row.get("is_deleted", False), Period.TOTAL) or {}


def _cards(manager, wtype):
    """The cards of the deck shown counted by lapses / reviews (charts.card_history)."""
    if getattr(manager, "_is_skeleton", False):
        return {}
    from ...widgets.charts.card_history import card_distribution

    row = getattr(manager, "last_row_data", None) or {}
    did = -1 if row.get("is_deleted") else row.get("did")
    return card_distribution(manager.addon_config, did, wtype)


def _due_today(manager):
    """The learning cards of the deck shown due today, by hour (charts.due_today)."""
    if getattr(manager, "_is_skeleton", False):
        return {}
    from ...widgets.charts.due_today import fetch

    row = getattr(manager, "last_row_data", None) or {}
    return fetch(manager.addon_config, row.get("did"), row.get("is_deleted", False))


def _payload(manager, wtype):
    kind = BY_TYPE[wtype].kind
    if kind == "today":
        return _due_today(manager)
    if kind == "intervals":
        return _intervals(manager)
    if kind == "cards":
        return _cards(manager, wtype)
    return _days(manager, wtype)  # (the "week" chart reads its counts for these days' period)


def _has_data(wtype, payload):
    if BY_TYPE[wtype].kind in ("intervals", "cards", "today"):
        return bool(payload and (payload.get("total", 0) or 0) > 0)
    return any((d.get("reviews", 0) or 0) > 0 for d in payload or [])


def _empty_allowed(manager):
    return bool(getattr(manager, "_is_skeleton", False) or getattr(manager, "_force_empty_build", False)
                or manager._show_empty_charts())


def build_section(manager, wtype):
    """(chart, header widget) of an added chart, for the section queue of populate_dashboard.
    (None, None) without data, as the other sections (it is then built empty and hidden)."""
    cfg = manager.addon_config
    adaptive = cfg.config.get(ADAPTIVE_CHART_BINNING, True)
    payload = _payload(manager, wtype)
    if not _has_data(wtype, payload) and not _empty_allowed(manager):
        return None, None
    if BY_TYPE[wtype].kind == "cards":
        from ...widgets.charts.card_history import CardCountChart

        chart = CardCountChart(wtype, payload, parent=manager.dialog, adaptive_binning=adaptive)
        chart.set_cumulative_mode(manager._get_dd_widget_setting(wtype, "show_cumulative", True))
        chart._dd_source = payload
    elif BY_TYPE[wtype].kind == "today":
        from ...widgets.charts.due_today import DueTodayChart

        chart = DueTodayChart(payload, cfg, parent=manager.dialog, adaptive_binning=adaptive)
        chart._dd_source = payload
        _row = getattr(manager, "last_row_data", None) or {}
        chart.set_source(cfg, _row.get("did"), _row.get("is_deleted", False))
    elif BY_TYPE[wtype].kind == "week":
        from ...widgets.charts.week_hours import WeekHoursChart

        chart = WeekHoursChart(cfg, parent=manager.dialog)
        _row = getattr(manager, "last_row_data", None) or {}
        chart.set_source(cfg, _row.get("did"), _row.get("is_deleted", False))
        chart.set_payload(payload)
        chart._dd_source = payload
    elif BY_TYPE[wtype].kind == "intervals":
        from ...widgets.charts.interval_load import IntervalLoadChart

        chart = IntervalLoadChart(payload, parent=manager.dialog, adaptive_binning=adaptive)
        chart.set_cumulative_mode(manager._get_dd_widget_setting(wtype, "show_cumulative", True))
        chart._dd_source = payload
    else:
        _row = getattr(manager, "last_row_data", None) or {}
        chart = DailyMetricChart(DAILY_BY_TYPE[wtype], payload, cfg, parent=manager.dialog,
                                 adaptive_binning=adaptive,
                                 source=(_row.get("did"), _row.get("is_deleted", False)),
                                 alt=bool(manager._get_dd_widget_setting(wtype, "alt_view", False)))
    chart._chart_owner = "deep_dive"
    chart._dd_deck = getattr(manager, "last_deck_identifier", None)
    if hasattr(chart, "set_hidden_series"):
        chart.set_hidden_series(manager._get_dd_widget_setting(wtype, "hidden_series", None))
    if hasattr(chart, "set_percent_mode") and getattr(chart, "metric", None) is not None and chart.metric.percent:
        chart.set_percent_mode(bool(manager._get_dd_widget_setting(wtype, "show_percent", False)))
    chart.binning_override = manager._get_dd_widget_setting(wtype, "binning_override", None)
    if BY_TYPE[wtype].kind == "today":
        chart.apply_options(False, False, manager._get_dd_widget_setting(wtype, "show_cumulative", True))
    elif hasattr(chart, "apply_options"):
        chart.apply_options(
            manager._get_dd_widget_setting(wtype, "show_average", True),
            manager._get_dd_widget_setting(wtype, "avg_on_active_days", True),
            manager._get_dd_widget_setting(wtype, "show_cumulative", True),
        )
    apply_chart_display_config(
        chart,
        opacity=manager._get_dd_widget_setting(wtype, "chart_opacity", 100),
        line_opacity=manager._get_dd_widget_setting(wtype, "line_opacity", None),
        bar_gradient=manager._get_dd_widget_setting(wtype, "bar_gradient", None),
        show_grid=manager._get_dd_widget_setting(wtype, "show_grid", None),
        tooltip_hidden=manager._get_dd_widget_setting(wtype, "tooltip_hidden", None),
        minimum_height=120,
        expanding=True,
    )
    header_widget, header_lay, _, stats_state = create_chart_header_for_chart(
        chart, cfg, Config.DEEP_DIVE_SHOW_BOTTOM_STATS, Config.DEEP_DIVE_SHOW_STATS, parent=manager.dialog,
    )
    metric = getattr(chart, "metric", None)
    if header_lay is not None and metric is not None and getattr(metric, "alt", None):
        # The other split of the same bars (Introduced: "By First Rating").
        from ....i18n import tr_name

        alt_cb = manager._make_styled_checkbox(tr_name(metric.alt[0]),
                                               checked=bool(manager._get_dd_widget_setting(wtype, "alt_view", False)),
                                               parent=header_widget)

        def _on_alt(checked, c=chart, h=header_widget):
            c.set_alt(checked)
            refresh_chart_header_stats(h, c)
            manager._update_dd_widget_setting(wtype, "alt_view", bool(checked), refresh=False)

        alt_cb.toggled.connect(_on_alt)
        header_lay.addWidget(alt_cb)
    if header_lay is not None and hasattr(chart, "zoom_changed"):
        header_lay.addWidget(_reset_button(manager, chart))
    if header_lay is not None and BY_TYPE[wtype].kind in ("intervals", "cards"):
        header_lay.addWidget(_filter_buttons(manager, wtype, chart, header_widget))
    connect_chart_header_refresh(chart, header_widget, enabled=stats_state["show_header_stats"])
    charts = getattr(manager, "_extra_charts", None)
    if charts is None:
        charts = manager._extra_charts = {}
    charts[wtype] = (chart, header_widget)
    return chart, header_widget


def _filter_buttons(manager, wtype, chart, header_widget):
    """The range buttons of Review Intervals (its "Range Buttons" settings, the choice kept)."""
    from ...widgets.common import (
        create_fsrs_filter_group,
        default_fsrs_filter_idx,
        resolve_fsrs_filter_choice,
        resolve_fsrs_filters,
    )

    modes, _short, labels = resolve_fsrs_filters(manager._get_dd_widget_setting(wtype, "filter_modes", None))
    idx, mode = resolve_fsrs_filter_choice(manager._get_dd_widget_setting(wtype, "time_span_idx"), modes=modes)
    chart.set_view_filter(mode)

    def applied(i):
        manager._update_dd_widget_setting(wtype, "time_span_idx", i, refresh=False)
        if hasattr(manager, "_refresh_bottom_stats"):
            manager._refresh_bottom_stats()

    return create_fsrs_filter_group(
        chart, labels=labels, resolved_idx=idx, make_radio_group=manager._make_radio_group,
        parent=header_widget, on_idx_applied=applied, modes=modes, default_idx=default_fsrs_filter_idx(modes),
    )


def _reset_button(manager, chart):
    """The chart's own zoom reset (shown while it is zoomed), like Added's."""
    btn = QPushButton("", parent=manager.dialog)
    btn.setIcon(get_svg_icon("rotate-ccw", context_ref=manager.dialog))
    btn.setIconSize(QSize(14, 14))
    btn.setFixedSize(20, 20)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setToolTip(tr("Reset Zoom"))
    btn.setVisible(False)
    btn.setProperty("class", "expanded_header_btn")

    def reset():
        chart.reset_zoom()
        chart.update()

    btn.clicked.connect(with_camera(reset))
    chart._dd_reset_btn = btn

    def changed(zoomed, _s, _e):
        # As Activity's own arrow: with the linked zoom on, the one Reset Zoom of the window
        # (update_all_reset_buttons) resets every chart, this arrow only shows with it off.
        update = getattr(manager, "update_all_reset_buttons", None)
        if update is not None:
            update()
        else:
            btn.setVisible(bool(zoomed))

    chart.zoom_changed.connect(changed)
    return btn


def update_reset_buttons(manager, sync):
    """Each added chart's arrow, and whether one of the linked ones is zoomed (the window's
    Reset Zoom then shows). A chart with no dates (Answer Time...) zooms alone: its arrow
    shows whenever it is zoomed."""
    linked = set(id(c) for c in zoom_linked_charts(manager))
    any_linked = False
    for _w, chart, _h in _shown_extras(manager):
        btn = getattr(chart, "_dd_reset_btn", None)
        zoomed = bool(getattr(chart, "_is_zoomed", False))
        is_linked = id(chart) in linked
        if zoomed and is_linked:
            any_linked = True
        if btn is not None:
            try:
                btn.setVisible(zoomed and (not sync or not is_linked))
            except RuntimeError:
                pass
    return any_linked


def queue_updates(manager, queue, candidates, span_and_days, animate_allowed):
    """New deck or period: queue the added charts' updates with the other charts' (see
    layout_parts.refresh_runtime), so they animate in the same batch, the same way.

    span_and_days(key): (span, custom days) of a section; animate_allowed(key): whether the
    refresh may animate it."""
    from ...widgets.charts.common.zoom import get_timespan_transition_meta, timespan_transition_mode

    cfg = manager.addon_config
    deck = getattr(manager, "last_deck_identifier", None)
    adaptive = cfg.config.get(ADAPTIVE_CHART_BINNING, True)
    # Charts that read their data themselves (in the background): read now, and the refresh
    # waits for them (refresh_runtime), so they animate in their turn with the others.
    pending = manager._dd_extra_pending = []
    for wtype, (chart, header) in list((getattr(manager, "_extra_charts", None) or {}).items()):
        try:
            same_deck = getattr(chart, "_dd_deck", deck) == deck
            if not same_deck and getattr(chart, "_is_zoomed", False) and hasattr(chart, "reset_zoom"):
                chart.reset_zoom()  # another deck: the zoomed days were the old deck's
            chart._dd_deck = deck
            if BY_TYPE[wtype].kind in ("intervals", "cards", "today", "week"):
                # The cards as they are now (not the period), as Review Intervals reads them;
                # Week by Hour: the day rows of the period (its counts are read for them).
                data = _payload(manager, wtype)
                old = getattr(chart, "_dd_source", None)
                chart._dd_source = data
                if hasattr(chart, "prefetch"):
                    _row = getattr(manager, "last_row_data", None) or {}
                    chart.set_source(cfg, _row.get("did"), _row.get("is_deleted", False))
                    if not chart.prefetch(data):
                        pending.append((chart, data))

                def apply(c=chart, d=data, h=header):
                    if hasattr(c, "set_payload"):
                        _row = getattr(manager, "last_row_data", None) or {}
                        c.set_source(cfg, _row.get("did"), _row.get("is_deleted", False))
                        c.set_payload(d)
                    else:
                        c.update_data(d, adaptive_binning=adaptive)
                    if h is not None:
                        refresh_chart_header_stats(h, c)

                manager._set_section_visible(wtype, _has_data(wtype, data) or manager._show_empty_charts())
                queue.append((chart, apply))
                if animate_allowed(wtype) and old != data:
                    candidates.append(chart)
                continue
            days = _days(manager, wtype)
            # No reviews in this period: hidden, as the other sections (unless empty charts show).
            manager._set_section_visible(wtype, _has_data(wtype, days) or manager._show_empty_charts())
            _row = getattr(manager, "last_row_data", None) or {}
            chart.set_source(_row.get("did"), _row.get("is_deleted", False))
            span, custom = span_and_days(wtype)
            token = (int(span), int(custom or 0))
            ready = chart.prefetch(days) if hasattr(chart, "prefetch") else True
            if not ready:
                pending.append((chart, days))
            prev_token = getattr(chart, "_last_timespan_token", token)
            prev_deck = getattr(chart, "_last_deck_id", deck)

            def apply(c=chart, d=days, h=header, tok=token, ptok=prev_token, pdeck=prev_deck, sp=span):
                # As Activity: another period slides the bars, another deck morphs them.
                # (Worked out now: the rows of the charts that read their own data are
                # only there once the refresh runs, see pending.)
                rows = c.rows_for(d)
                meta = get_timespan_transition_meta(
                    ptok,
                    tok,
                    prev_deck_id=pdeck,
                    current_deck_id=deck,
                    old_series=getattr(c, "_full_data", []),
                    new_series=rows,
                    total_span_active=(int(sp) == int(Period.TOTAL)),
                )
                c.set_days(d, adaptive_binning=adaptive, transition_mode=timespan_transition_mode(meta, deck_policy="ignore"))
                if h is not None:
                    refresh_chart_header_stats(h, c)

            queue.append((chart, apply))
            changed = (not ready) or list(getattr(chart, "_full_data", []) or []) != list(chart.rows_for(days))
            if animate_allowed(wtype) and changed:
                candidates.append(chart)
            chart._last_timespan_token = token
            chart._last_deck_id = deck
        except RuntimeError:
            manager._extra_charts.pop(wtype, None)  # deleted with its view
        except Exception:
            log_swallowed()

def _shown_extras(manager):
    out = []
    for wtype, (chart, header) in list((getattr(manager, "_extra_charts", None) or {}).items()):
        try:
            chart.isVisible()
        except RuntimeError:
            continue  # deleted with its view
        out.append((wtype, chart, header))
    return out


def zoom_linked_charts(manager):
    """The added charts of days (Forgotten, Introduced, Review Speed...): zoomed with
    Activity and the others to the same dates (runtime.zoom_sync)."""
    return [c for w, c, _h in _shown_extras(manager)
            if BY_TYPE[w].kind == "daily" and DAILY_BY_TYPE[w].by_day
            and getattr(c, "_zoom_linked", True) and hasattr(c, "zoom_changed")]


def _zoom_follower(wtype):
    """Charts of the period with no time axis (Week by Hour, Answer Time, Rating by
    Interval): they show the zoomed days, as Hourly Breakdown and Answer Buttons do."""
    kind = BY_TYPE[wtype].kind
    return kind == "week" or (kind == "daily" and not DAILY_BY_TYPE[wtype].by_day)


def follow_zoom(manager, dates):
    """Show the days dates=(first, last) in the charts that follow the zoom (None: their
    whole period). Run after the zoom animation, with the stats (runtime.zoom_sync)."""
    from ...ui.shared.zoom_span import _row_date
    from ...animations.chart_policy import local_chart_animation_batch

    cfg = manager.addon_config
    _row = getattr(manager, "last_row_data", None) or {}
    did, deleted = _row.get("did"), _row.get("is_deleted", False)
    jobs = []
    for wtype, chart, header in _shown_extras(manager):
        if not _zoom_follower(wtype):
            continue
        days = _days(manager, wtype)
        if dates is not None:
            def inside(row):
                d = _row_date(row)
                return d is not None and dates[0] <= d <= dates[1]

            try:
                days = [r for r in days if inside(r)]
            except TypeError:
                pass  # dates of another kind (the 10-minute view): the whole period
        if not days:
            continue
        jobs.append((wtype, chart, header, days))
    if not jobs:
        return
    charts = [j[1] for j in jobs]
    with local_chart_animation_batch(charts[0], candidates=charts):
        for wtype, chart, header, days in jobs:
            try:
                if BY_TYPE[wtype].kind == "week":
                    chart.set_source(cfg, did, deleted)
                    chart.set_payload(days)
                else:
                    chart.set_source(did, deleted)
                    chart.set_days(days)
                if header is not None:
                    refresh_chart_header_stats(header, chart)
            except RuntimeError:
                pass
            except Exception:
                log_swallowed()

def _rebuild(manager):
    if not getattr(manager, "last_row_data", None):
        return
    manager._cleanup_previous_view()
    manager._populate_dashboard()
    manager._setup_zoom_sync()


def _save(manager, types):
    manager.addon_config.set_value(Config.DEEP_DIVE_EXTRA_CHARTS, list(types))


def _save_hidden(manager, types):
    manager.addon_config.set_value(Config.DEEP_DIVE_HIDDEN_CHARTS, list(types))


def _show(manager, wtype, index=None):
    if wtype in base_types():
        _save_hidden(manager, [t for t in hidden_types(manager) if t != wtype])
    elif wtype in BY_TYPE:
        types = extra_types(manager)
        if wtype not in types:
            types.insert(len(types) if index is None else min(index, len(types)), wtype)
            _save(manager, types)


def remove_chart(manager, wtype):
    """Any chart off Deep Dive, with the Undo note (back at the same place). A usual one
    comes back with Add Chart too; its settings (size, options) stay."""
    if wtype in base_types():
        if wtype in hidden_types(manager):
            return
        _save_hidden(manager, hidden_types(manager) + [wtype])
        index = None
    else:
        types = extra_types(manager)
        if wtype not in types:
            return
        index = types.index(wtype)
        _save(manager, [t for t in types if t != wtype])
    window = manager.dialog.window()
    _rebuild(manager)

    def undo():
        _show(manager, wtype, index)
        _rebuild(manager)

    from ...widgets.pinned.main_menu.ui.undo_toast import show_undo_toast

    show_undo_toast(tr("Widget removed"), undo, window=window)


def can_add(manager):
    """The charts not in Deep Dive now: the usual ones removed, then the others."""
    return hidden_types(manager) + [m.widget_type for m in CHARTS if m.widget_type not in extra_types(manager)]


def _stat_cards(manager):
    """The Deep Dive stat cards (the dashboard's, shown in Deep Dive) that can be added or removed."""
    container = getattr(manager.dialog, "stats_container", None)
    cards = list(getattr(container, "cards", None) or [])
    return container, [c for c in cards if getattr(c, "config_key", None)]


def _card_shown(manager, key):
    return bool(manager.addon_config.config.get(key, True))


def _refresh_cards(manager, container):
    if hasattr(manager.dialog, "update_dashboard_visibility"):
        manager.dialog.update_dashboard_visibility()
    try:
        width = manager.dialog.width()
        if container is not None and width > 0:
            container.update_layout(width)
    except Exception:
        log_swallowed()


def _show_card(manager, card, on, at_end=True):
    """A stat card on or off (as Remove does); one put back on goes at the end."""
    container, _cards = _stat_cards(manager)
    if on and at_end and hasattr(container, "place_at_end"):
        container.place_at_end(card)
    card.setVisible(on)
    card.setHidden(not on)
    manager.addon_config.set_value(card.config_key, on)


def _set_card(manager, key, on):
    container, cards = _stat_cards(manager)
    card = next((c for c in cards if c.config_key == key), None)
    if card is None or on == _card_shown(manager, key):
        return
    _show_card(manager, card, on)
    _refresh_cards(manager, container)


def _set_chart(manager, wtype, on):
    if on:
        _show(manager, wtype)  # a new one at the end
    elif wtype in base_types():
        if wtype not in hidden_types(manager):
            _save_hidden(manager, hidden_types(manager) + [wtype])
    else:
        _save(manager, [t for t in extra_types(manager) if t != wtype])
    _schedule_rebuild(manager)


def _schedule_rebuild(manager):
    """One rebuild for a few quick clicks."""
    timer = getattr(manager, "_dd_manage_timer", None)
    try:
        if timer is None:
            timer = QTimer(manager.dialog)
            timer.setSingleShot(True)
            timer.setInterval(250)
            timer.timeout.connect(lambda: _rebuild(manager))
            manager._dd_manage_timer = timer
        timer.start()
    except RuntimeError:
        manager._dd_manage_timer = None


def _snapshot(manager):
    import copy

    container, cards = _stat_cards(manager)
    conf = manager.addon_config.config
    return {
        "hidden": hidden_types(manager),
        "extra": extra_types(manager),
        "cards": {c.config_key: _card_shown(manager, c.config_key) for c in cards},
        "layout": container.layout_state() if hasattr(container, "layout_state") else None,
        # Order and sizes ("Reset to Default" changes them too).
        "order": copy.deepcopy(conf.get(Config.DEEP_DIVE_CHART_ORDER)),
        "sizes": copy.deepcopy(conf.get(Config.DEEP_DIVE_WIDGET_SETTINGS)),
    }


def _reset_default(manager):
    """The default Deep Dive: its usual charts and stat cards, in the default order and
    size. Returns (chart types, stat card keys) shown."""
    container, cards = _stat_cards(manager)
    for c in cards:
        default = bool(Config.DEFAULT_CONFIG.get(c.config_key, True))
        if default != _card_shown(manager, c.config_key):
            _show_card(manager, c, default, at_end=False)
    _refresh_cards(manager, container)
    _save_hidden(manager, [])
    _save(manager, [])
    manager._reset_chart_order(rebuild=False)  # order and sizes
    _rebuild(manager)
    return shown_charts(manager), [c.config_key for c in cards if _card_shown(manager, c.config_key)]


def _restore(manager, snap):
    """Cancel: the charts and stat cards as they were when the manager opened."""
    timer = getattr(manager, "_dd_manage_timer", None)
    try:
        if timer is not None:
            timer.stop()
    except RuntimeError:
        pass
    container, cards = _stat_cards(manager)
    for c in cards:
        was = snap["cards"].get(c.config_key)
        if was is not None and was != _card_shown(manager, c.config_key):
            _show_card(manager, c, was, at_end=False)
    if snap["layout"] is not None and hasattr(container, "restore_layout_state"):
        container.restore_layout_state(snap["layout"])
    _refresh_cards(manager, container)
    conf = manager.addon_config.config
    layout_changed = (conf.get(Config.DEEP_DIVE_CHART_ORDER) != snap["order"]
                      or conf.get(Config.DEEP_DIVE_WIDGET_SETTINGS) != snap["sizes"])
    if layout_changed:
        for key, value in ((Config.DEEP_DIVE_CHART_ORDER, snap["order"]),
                           (Config.DEEP_DIVE_WIDGET_SETTINGS, snap["sizes"])):
            if value is None:
                conf.pop(key, None)
            else:
                conf[key] = value
        manager.addon_config.write_config()
    if layout_changed or hidden_types(manager) != snap["hidden"] or extra_types(manager) != snap["extra"]:
        _save_hidden(manager, snap["hidden"])
        _save(manager, snap["extra"])
        _rebuild(manager)


def shown_charts(manager):
    hidden = set(hidden_types(manager))
    return [t for t in base_types() if t not in hidden] + extra_types(manager)


def open_gallery(manager, family="chart"):
    """The gallery as the manager of Deep Dive: every chart and stat card, the ones shown
    checked; a click adds or removes one at once, Cancel puts everything back."""
    from ...widgets.pinned.main_menu.manager import MainMenuWidgetManager
    from ...widgets.pinned.main_menu.ui.widget_gallery import open_manage_gallery

    _container, cards = _stat_cards(manager)
    keys = [c.config_key for c in cards]
    try:
        parent = manager.dialog.window()
    except RuntimeError:
        return
    snap = _snapshot(manager)
    changed = {"cards": False}

    def toggle(choice, on):
        if choice.family == "stat":
            _set_card(manager, choice.stat_key, on)
            changed["cards"] = True
        elif choice.family == "chart":
            _set_chart(manager, choice.widget_type, on)

    result = open_manage_gallery(
        MainMenuWidgetManager.instance(), parent,
        charts=base_types() + [m.widget_type for m in CHARTS],
        charts_shown=shown_charts(manager),
        stats=keys, stats_shown=[k for k in keys if _card_shown(manager, k)],
        family=family, on_toggle=toggle,
        on_reset=lambda: _reset_default(manager),
    )
    if result is None:
        _restore(manager, snap)
    if changed["cards"] and MainMenuWidgetManager.instance_exists():
        MainMenuWidgetManager.instance().refresh()


def add_button(manager):
    """The "Add or remove" button of the Deep Dive header (next to the zoom and settings)."""
    # Icon and name: the icon alone, next to the zoom's - and +, did not say what it opens.
    btn = QPushButton(" " + tr("Charts"), parent=manager.dialog)
    btn.setIcon(get_svg_icon("chart-plus", context_ref=manager.dialog))
    btn.setIconSize(QSize(16, 16))
    btn.setFixedHeight(24)
    set_qss(btn, "QPushButton { padding: 0px 6px; }")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setToolTip(tr("Add or Remove Charts and Stat Cards"))
    btn.setProperty("class", "expanded_header_btn")
    btn.clicked.connect(lambda: QTimer.singleShot(0, lambda: open_gallery(manager)))
    return btn


# -- the "Add Chart" spot in the free end of the last row (on hover) ----------------------

class _AddSpot(QFrame):
    """A dashed card with "+ Add Chart", shown while the mouse is over the free slots at the
    end of the last row of charts (it never takes a row of its own)."""

    def __init__(self, manager, parent):
        super().__init__(parent)
        self._manager = manager
        self.setObjectName("dd_add_chart_spot")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        dark = bool((getattr(manager, "theme_vars", None) or {}).get("is_dark", True))
        line = "rgba(255,255,255,0.18)" if dark else "rgba(0,0,0,0.18)"
        fill = "rgba(255,255,255,0.03)" if dark else "rgba(0,0,0,0.025)"
        text = "rgba(255,255,255,0.6)" if dark else "rgba(0,0,0,0.55)"
        set_qss(self,
            f"QFrame#dd_add_chart_spot {{ border: 1px dashed {line}; border-radius: 12px; background: {fill}; }}"
            f"QLabel {{ color: {text}; background: transparent; border: none; }}")
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        plus = QLabel("+")
        set_qss(plus, "font-size: 28px;")
        plus.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label = QLabel(tr("Add Chart"))
        set_qss(label, "font-size: 13px; font-weight: 600;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(plus)
        lay.addWidget(label)
        self.hide()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.hide()
            # Once this click is over: the gallery rebuilds the charts, this spot with them
            # (deleted while still in its own click, it was an error).
            manager = self._manager
            QTimer.singleShot(0, lambda: open_gallery(manager))
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        self.hide()
        super().leaveEvent(event)


class _SpotHover(QObject):
    """Shows the spot while the mouse is over the free slots of the grid's last row."""

    def __init__(self, manager, container, layout):
        super().__init__(container)
        self._manager = manager
        self._container = container
        self._layout = layout
        self.spot = _AddSpot(manager, container)
        container.setMouseTracking(True)
        container.installEventFilter(self)

    def _rect(self):
        slot = getattr(self._layout, "free_slot", None)
        if slot is None or not can_add(self._manager):  # nothing left to add: no spot
            return None
        x, y, w, h, _n = slot
        return QRect(int(x), int(y), int(w), int(max(80, h)))

    def eventFilter(self, obj, event):
        try:
            kind = event.type()
            if kind == QEvent.Type.MouseMove:
                rect = self._rect()
                inside = rect is not None and rect.contains(event.position().toPoint())
                if inside and not self.spot.isVisible():
                    self.spot.setGeometry(rect)
                    self.spot.show()
                    self.spot.raise_()
                elif not inside and self.spot.isVisible():
                    self.spot.hide()
            elif kind in (QEvent.Type.Leave, QEvent.Type.Hide) and not self.spot.underMouse():
                self.spot.hide()
        except RuntimeError:
            pass
        return False


def install_add_spot(manager, container, layout):
    """Once per grid (populate_dashboard)."""
    try:
        manager._dd_add_spot = _SpotHover(manager, container, layout)
    except Exception:
        log_swallowed()
