# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..utils import _addon_config, _make_checkbox
from . import pinned_title
from ..wrapper import _wrap
from . import Period
from ..shared.header import prepare_pinned_header
from ..shared.context import get_pinned_context_value
from .....logic.data.section_fetchers import fetch_section_data
from .....logic.data.section_fallbacks import resolve_card_counts_payload
from ....charts.pie_chart import PieChartWidget
from ....common import apply_chart_display_config, create_chart_header
from ...store.registry import WidgetRegistry
from .....logic.logger import log_swallowed


def _build_card_counts(widget_def, deck_id, cache=None, parent=None, cfg=None):
    config = cfg or _addon_config()
    _, history = get_pinned_context_value(
        deck_id,
        Period.TOTAL,
        "counts",
        cfg=config,
        allow_slow_ops=False,
    )
    counts = resolve_card_counts_payload(
        {"counts": history} if history is not None else None,
        fetcher=lambda: fetch_section_data(config, "card_counts", deck_id=deck_id),
        fetch_when_empty=False,
        fetch_when_non_deleted_zero_total=False,
    )
    chart = PieChartWidget(counts, parent=parent)
    # PieChartWidget caches its colors early; make sure pinned theme context is explicit
    # even before the widget is wrapped into a themed card.
    chart.setProperty("deepdivestats_theme_context", "pinned")
    chart.setProperty("deepdivestats_ignore_forced_dark_theme", True)
    if hasattr(chart, "refresh_data_colors"):
        try:
            chart.refresh_data_colors()
        except Exception:
            log_swallowed()
    apply_chart_display_config(
        chart,
        opacity=widget_def.get("chart_opacity", 100),
        line_opacity=widget_def.get("line_opacity"),
        bar_gradient=widget_def.get("bar_gradient"),
        show_grid=widget_def.get("show_grid"),
        minimum_height=200,
    )

    sep_susp = widget_def.get("separate_suspended", True)
    chart.set_separate_suspended(sep_susp)
    chart.set_show_legend(widget_def.get("show_legend", True))
    chart.set_legend_mode(widget_def.get("legend_mode", "auto"))

    header_widget, header_lay, _ = create_chart_header(
        parent=parent,
        title=pinned_title(widget_def, "CARD COUNTS"),
        title_object_name="pinned_header",
    )
    prepare_pinned_header(header_widget, header_lay)

    wid = widget_def["id"]

    cb_sep = _make_checkbox("Sep. Susp.", checked=sep_susp, parent=header_widget)

    def on_sep_toggle(state, w=wid):
        val = bool(state)
        chart.set_separate_suspended(val)
        WidgetRegistry.update_setting(w, "separate_suspended", val)
        widget_def["separate_suspended"] = val

    cb_sep.stateChanged.connect(on_sep_toggle)
    header_lay.addWidget(cb_sep)

    return _wrap(
        chart,
        pinned_title(widget_def, "CARD COUNTS").upper(),
        header_widget=header_widget,
        widget_id=widget_def["id"],
        saved_w=widget_def.get("width"),
        saved_h=widget_def.get("height"),
        parent=parent,
    )


def _update_card_counts(chart, widget_def, deck_id, cache=None, fail_if_not_cached=False, cfg=None):
    # Fast path: use already-warmed context cache (non-blocking).
    config = cfg or _addon_config()
    _, counts = get_pinned_context_value(
        deck_id,
        Period.TOTAL,
        "counts",
        cfg=config,
        allow_slow_ops=False,
    )

    counts = resolve_card_counts_payload(
        {"counts": counts} if counts is not None else None,
        fetcher=(
            None
            if fail_if_not_cached
            else lambda: fetch_section_data(config, "card_counts", deck_id=deck_id)
        ),
        fetch_when_empty=False,
        fetch_when_non_deleted_zero_total=False,
    )

    if counts is None:
        return False
    if hasattr(chart, "set_show_legend"):
        chart.set_show_legend(widget_def.get("show_legend", True))
    if hasattr(chart, "set_legend_mode"):
        chart.set_legend_mode(widget_def.get("legend_mode", "auto"))
    if hasattr(chart, "update_counts"):
        chart.update_counts(counts)
        return True
    return False


