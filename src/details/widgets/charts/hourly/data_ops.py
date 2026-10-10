# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QColor, QEasingCurve

from ...chart_utils.formatting import fmt_num, fmt_num_compact
from ..common.discrete import set_chart_opacity_impl
from ..common.core import set_flag_and_update


def set_cumulative_mode_impl(widget, visible):
    return set_flag_and_update(widget, "show_cumulative_axis", bool(visible))


def get_margin_right_impl(widget):
    return 35 if bool(getattr(widget, "show_cumulative_axis", True)) else 10


def snapshot_from_data_impl(widget, data_dict):
    totals = []
    correct = []
    src = data_dict or {}
    for h_idx in range(24):
        d = src.get(h_idx, {})
        totals.append(float(d.get("total", 0) or 0.0))
        correct.append(float(d.get("correct", 0) or 0.0))
    return totals, correct


def interpolate_series_fast_impl(widget, old_values, new_values, t):
    return [max(0.0, ov + ((nv - ov) * t)) for ov, nv in zip(old_values, new_values)]


def current_values_snapshot_impl(widget):
    if not widget._data_transition_active:
        return widget._snapshot_from_data(widget.data_dict)
    t = widget.get_progress()
    if t >= 0.995:
        t = 1.0
    totals = widget._interpolate_series_fast(widget._transition_old_totals, widget._transition_new_totals, t)
    correct = widget._interpolate_series_fast(widget._transition_old_correct, widget._transition_new_correct, t)
    return totals, correct

def refresh_data_colors_impl(widget):
    from ....ui import Config, get_chart_color

    widget.bar_color = QColor(get_chart_color(Config.COLOR_BAR, widget))


def update_data_impl(widget, new_data):
    old_totals, old_correct = widget._current_values_snapshot()
    new_totals, new_correct = widget._snapshot_from_data(new_data)
    old_max = max(old_totals) if old_totals and max(old_totals) > 0 else 1.0
    new_max = max(new_totals) if new_totals and max(new_totals) > 0 else 1.0

    widget.data_dict = new_data
    widget.max_val = max([v["total"] for v in widget.data_dict.values()]) if widget.data_dict else 1
    if widget.max_val == 0:
        widget.max_val = 1
    widget._clear_hover()
    if old_totals != new_totals or old_correct != new_correct:
        transition_slots = []
        old_draw_ratios = []
        new_draw_ratios = []
        for h_idx in range(24):
            ot = old_totals[h_idx] if h_idx < len(old_totals) else 0.0
            nt = new_totals[h_idx] if h_idx < len(new_totals) else 0.0
            oc = old_correct[h_idx] if h_idx < len(old_correct) else 0.0
            nc = new_correct[h_idx] if h_idx < len(new_correct) else 0.0
            old_active = ot > 0.0
            new_active = nt > 0.0
            old_rate = (oc / ot) if old_active else 0.0
            new_rate = (nc / nt) if new_active else 0.0
            old_draw_ratios.append(max(0.0, ot / old_max))
            new_draw_ratios.append(max(0.0, nt / new_max))
            transition_slots.append(
                {
                    "old_active": old_active,
                    "new_active": new_active,
                    "old_rate": old_rate,
                    "new_rate": new_rate,
                    "fades_to_empty": bool(old_active and not new_active),
                }
            )

        widget._transition_old_totals = old_totals
        widget._transition_new_totals = new_totals
        widget._transition_old_correct = old_correct
        widget._transition_new_correct = new_correct
        widget._transition_old_max = old_max
        widget._transition_new_max = new_max
        widget._data_transition_render_cache = {
            "transition_slots": transition_slots,
            "old_draw_ratios": old_draw_ratios,
            "new_draw_ratios": new_draw_ratios,
        }
        widget._data_transition_active = True
        widget.animate_data_update(
            old_totals,
            new_totals,
            min_duration_ms=210,
            max_duration_ms=210,
            empty_transition_duration_ms=210,
        )
        widget.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    else:
        widget._data_transition_active = False
        widget._transition_old_totals = [0.0] * 24
        widget._transition_new_totals = [0.0] * 24
        widget._transition_old_correct = [0.0] * 24
        widget._transition_new_correct = [0.0] * 24
        widget._transition_old_max = 1.0
        widget._transition_new_max = 1.0
        widget._data_transition_render_cache = {}
        widget._progress = 1.0
        widget.animation.stop()
        widget.maybe_start_initial_animation()
    widget.update()


def get_tooltip_text_impl(widget, h_idx):
    d = widget.data_dict.get(h_idx, {})
    total = d.get("total", 0)
    correct = d.get("correct", 0)
    if total > 0:
        rate = (correct / total * 100)
        total_int = int(round(float(total)))
        total_txt = fmt_num(total_int) if abs(float(total) - total_int) < 1e-9 else fmt_num(total)
        return f"{h_idx}:00 - {h_idx}:59\nReviews: {total_txt}\nCorrect: {rate:.1f}%"
    return f"{h_idx}:00 - {h_idx}:59\nReviews: 0"


def get_stats_text_impl(widget):
    totals, correct = widget._current_values_snapshot()
    total_revs = sum(float(v or 0.0) for v in (totals or []))
    total_correct = sum(float(v or 0.0) for v in (correct or []))
    if total_revs > 0:
        rate = (total_correct / total_revs * 100)
        return [f"Total: {fmt_num_compact(total_revs)} revs", f"Retention: {fmt_num_compact(rate)}%"]
    return [f"Total: {fmt_num_compact(total_revs)} revs", "Retention: -"]
