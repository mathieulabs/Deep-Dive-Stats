# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import math

from .series import SERIES_KEYS
from ...chart_utils import ChartGeometry
from ...chart_utils.binning import get_bin_size
from ...chart_utils.formatting import fmt_num_compact
from ..common.discrete import binning_active_getter, set_chart_opacity_impl
from ..common.core import set_flag_and_update
from ....animations.chart_policy import chart_animations_allowed
from ....logic.logger import log_swallowed


def _range_for_display_data(display_data, visible_series):
    all_vals = []
    for key in SERIES_KEYS:
        if not visible_series.get(key, False):
            continue
        for item in (display_data.get(key) or []):
            v = item[1] if isinstance(item, (list, tuple)) else item
            if v is not None:
                all_vals.append(float(v))
    if not all_vals:
        return 0.0, 100.0
    # Whole percents: the axis labels are then round numbers, not "0.0" for a 0.03% low.
    lo = float(math.floor(min(all_vals)))
    hi = float(math.ceil(max(all_vals)))
    if hi <= lo:
        hi = lo + 1.0
    return lo, hi


CURVE_DIV = 4


def _curve_values(filled, mask, div=CURVE_DIV):
    """The values of the rounded line, `div` steps per segment.

    Same monotone curve as the one drawn at rest: it goes through the real points
    (mask) only, so the line keeps its curvature while it morphs.
    """
    n = len(filled)
    out = []
    for i in range(n - 1):
        out.extend([filled[i]] * div)
    out.append(filled[-1])
    for i in range(n - 1):
        for s in range(1, div):
            t = s / div
            out[i * div + s] = filled[i] + (filled[i + 1] - filled[i]) * t
    i = 0
    while i < n:
        if mask[i] <= 0.5:
            i += 1
            continue
        j = i
        while j + 1 < n and mask[j + 1] > 0.5:
            j += 1
        if j > i:
            vals = filled[i:j + 1]
            m_ = len(vals)
            d_ = [vals[k + 1] - vals[k] for k in range(m_ - 1)]
            m = [0.0] * m_
            m[0], m[-1] = d_[0], d_[-1]
            for k in range(1, m_ - 1):
                if d_[k - 1] * d_[k] <= 0:
                    m[k] = 0.0
                else:
                    m[k] = 2.0 / (1.0 / d_[k - 1] + 1.0 / d_[k])
            for k in range(m_ - 1):
                y0, y1, m0, m1 = vals[k], vals[k + 1], m[k], m[k + 1]
                for s in range(1, div):
                    t = s / div
                    t2, t3 = t * t, t * t * t
                    out[(i + k) * div + s] = (
                        (2 * t3 - 3 * t2 + 1) * y0 + (t3 - 2 * t2 + t) * m0
                        + (-2 * t3 + 3 * t2) * y1 + (t3 - t2) * m1
                    )
        i = j + 1
    return out



def clear_data_transition_state_impl(widget):
    widget._data_transition_active = False
    widget._data_transition_old_series = {}
    widget._data_transition_new_series = {}
    widget._data_transition_sample_count = 0
    widget._data_transition_old_labels = []
    widget._data_transition_old_display_data = {}
    widget._data_transition_new_display_data = {}
    widget._data_transition_render_cache = {}
    widget._data_transition_old_range = (0.0, 100.0)
    widget._data_transition_new_range = (0.0, 100.0)

def set_average_mode_impl(widget, visible, on_active_days=True):
    widget.avg_visible = visible
    widget.avg_on_active_days = on_active_days
    widget._calc_averages()
    widget.update()


def set_cumulative_mode_impl(widget, visible):
    return set_flag_and_update(widget, "cumulative_visible", bool(visible))


def set_show_stats_impl(widget, enabled):
    return set_flag_and_update(widget, "show_stats", enabled)


def update_data_impl(widget, new_ret_data, adaptive_binning=None, transition=False, transition_duration_ms=220):
    if not chart_animations_allowed(widget):
        transition = False
    if getattr(widget, "_keep_zoom", None):
        # The zoom is restored right after this update (deck change). The transition is
        # built on the full range, so playing it would show the zoom reset first.
        transition = False

    def _series_stats(payload):
        payload = payload or {}
        out = {}
        for k in SERIES_KEYS:
            series = payload.get(k) or []
            out[f"{k}_len"] = len(series) if isinstance(series, list) else 0
            vals = []
            if isinstance(series, list):
                for item in series:
                    if isinstance(item, (list, tuple)) and len(item) >= 2 and isinstance(item[1], (int, float)):
                        vals.append(float(item[1]))
            out[f"{k}_sum"] = round(float(sum(vals)), 4) if vals else 0.0
        return out

    # The stats of the previous payload were computed by the last update: reuse them.
    last = getattr(widget, "_last_series_stats", None)
    if last is not None and last[0] is widget.retention_data:
        old_stats = last[1]
    else:
        old_stats = _series_stats(widget.retention_data if isinstance(widget.retention_data, dict) else {})
    new_stats = _series_stats(new_ret_data if isinstance(new_ret_data, dict) else {})
    widget._last_series_stats = (new_ret_data or {}, new_stats)
    old_total = float(sum(old_stats.get(f"{k}_sum", 0.0) for k in SERIES_KEYS))
    new_total = float(sum(new_stats.get(f"{k}_sum", 0.0) for k in SERIES_KEYS))
    if transition and (not bool(getattr(widget, "_initial_animation_done", False))) and old_total <= 0.0 and new_total > 0.0:
        transition = False

    transition_payload = None
    if transition and widget.isVisible() and widget.width() > 0 and widget.height() > 0:
        transition_payload = widget._prepare_data_transition(new_ret_data or {})

    if adaptive_binning is not None:
        widget.adaptive_binning = adaptive_binning
    widget._full_retention_data = new_ret_data or {}
    widget.retention_data = new_ret_data or {}

    data_length = 0
    for key in widget.retention_data:
        if widget.retention_data[key]:
            data_length = len(widget.retention_data[key])
            break

    widget.init_zoom(data_length)
    widget._path_cache = {}
    widget._margin_cache = None
    widget._labels_cache = None
    widget._binned_data_cache = None
    widget._calc_averages()
    _notify_totals(widget)

    if transition_payload is not None:
        (
            old_series,
            new_series,
            sample_count,
            old_labels,
            new_labels,
            old_display_data,
            new_display_data,
            render_cache,
            old_range,
            new_range,
        ) = transition_payload
        widget._data_transition_active = True
        widget._data_transition_old_series = old_series
        widget._data_transition_new_series = new_series
        widget._data_transition_sample_count = sample_count
        widget._data_transition_old_labels = old_labels
        widget._data_transition_old_display_data = old_display_data
        widget._data_transition_new_display_data = new_display_data
        widget._data_transition_render_cache = render_cache
        widget._data_transition_old_range = old_range
        widget._data_transition_new_range = new_range
        widget.animation.stop()
        widget.animation.setDuration(max(100, int(transition_duration_ms)))
        widget._progress = 0.0
        widget.animation.start()
    else:
        widget._clear_data_transition_state()
        widget.maybe_start_initial_animation()

    widget.update()


def on_animation_finished_impl(widget):
    if widget._data_transition_active:
        widget._clear_data_transition_state()
        widget.animation.setDuration(600)
        widget._progress = 1.0
        widget.update()


def extract_series_values_impl(widget, series_data):
    values = []
    for item in series_data or []:
        if isinstance(item, (list, tuple)):
            values.append(item[1] if len(item) >= 2 else None)
        else:
            values.append(item)
    return values


def sample_series_values_impl(widget, values, sample_count):
    if sample_count <= 0:
        return []
    if not values:
        return [None] * sample_count
    if sample_count == 1:
        return [values[-1]]
    if len(values) == 1:
        sampled = [None] * sample_count
        sampled[0] = values[0]
        return sampled

    last_idx = len(values) - 1
    sampled = []
    for i in range(sample_count):
        src_idx = int(round(i * last_idx / (sample_count - 1)))
        sampled.append(values[src_idx])
    return sampled


def prepare_data_transition_impl(widget, new_ret_data):
    old_display_data = widget._get_display_data()
    new_display_data = widget._compute_display_data(new_ret_data or {})

    old_display_n = 0
    new_display_n = 0
    for key in SERIES_KEYS:
        if old_display_n == 0 and old_display_data.get(key):
            old_display_n = len(old_display_data[key])
        if new_display_n == 0 and new_display_data.get(key):
            new_display_n = len(new_display_data[key])
    if new_display_n < 2:
        return None

    sample_count = new_display_n
    if sample_count < 2:
        return None

    old_series = {}
    new_series = {}
    has_any_value = False
    for key in widget.SERIES_CONFIG:
        old_vals = widget._extract_series_values(old_display_data.get(key, []))
        new_vals = widget._extract_series_values(new_display_data.get(key, []))
        old_sampled = widget._sample_series_values(old_vals, sample_count)
        new_sampled = widget._sample_series_values(new_vals, sample_count)
        if any(v is not None for v in old_sampled) or any(v is not None for v in new_sampled):
            has_any_value = True
        old_series[key] = old_sampled
        new_series[key] = new_sampled

    if not has_any_value:
        return None

    def _fill_missing(values):
        mask = []
        known = []
        for idx in range(sample_count):
            v = values[idx] if idx < len(values) else None
            is_known = v is not None
            mask.append(1.0 if is_known else 0.0)
            if is_known:
                known.append((idx, float(v)))
        if not known:
            return [0.0] * sample_count, mask
        filled = [0.0] * sample_count
        first_idx, first_val = known[0]
        for i in range(0, first_idx + 1):
            filled[i] = first_val
        for j in range(len(known) - 1):
            a_idx, a_val = known[j]
            b_idx, b_val = known[j + 1]
            span = b_idx - a_idx
            if span <= 0:
                continue
            filled[a_idx] = a_val
            for k in range(1, span):
                t = k / span
                filled[a_idx + k] = a_val + ((b_val - a_val) * t)
            filled[b_idx] = b_val
        last_idx, last_val = known[-1]
        for i in range(last_idx, sample_count):
            filled[i] = last_val
        return filled, mask

    render_cache = {}
    for key in widget.SERIES_CONFIG:
        old_filled, old_mask = _fill_missing(old_series.get(key, []))
        new_filled, new_mask = _fill_missing(new_series.get(key, []))
        segment_meta = []
        for i in range(max(0, sample_count - 1)):
            old_pair = old_mask[i] > 0.5 and old_mask[i + 1] > 0.5
            new_pair = new_mask[i] > 0.5 and new_mask[i + 1] > 0.5
            seg_fades_to_empty = old_pair and not new_pair
            is_old_left_edge = (i == 0) or (old_mask[i - 1] < 0.5)
            is_old_right_edge = (i + 1 == sample_count - 1) or (old_mask[i + 2] < 0.5)
            segment_meta.append(
                {
                    "candidate": bool(old_pair or new_pair),
                    "edge_fade": bool(seg_fades_to_empty and (is_old_left_edge or is_old_right_edge)),
                }
            )

        point_meta = []
        for i in range(sample_count):
            old_isolated = (
                old_mask[i] > 0.5
                and (i == 0 or old_mask[i - 1] < 0.5)
                and (i == sample_count - 1 or old_mask[i + 1] < 0.5)
            )
            new_isolated = (
                new_mask[i] > 0.5
                and (i == 0 or new_mask[i - 1] < 0.5)
                and (i == sample_count - 1 or new_mask[i + 1] < 0.5)
            )
            point_meta.append(
                {
                    "candidate": bool(old_isolated or new_isolated),
                    "appears_from_empty": bool(old_mask[i] < 0.5 and new_isolated),
                    "fades_to_empty": bool(old_isolated and new_mask[i] < 0.5),
                    "edge_point": bool((i == 0) or (i == sample_count - 1)),
                }
            )

        render_cache[key] = {
            "old_filled": old_filled,
            "new_filled": new_filled,
            "old_mask": old_mask,
            "new_mask": new_mask,
            "old_curve": _curve_values(old_filled, old_mask),
            "new_curve": _curve_values(new_filled, new_mask),
            "old_avg": widget._avg_from_display_series(old_display_data.get(key, [])),
            "new_avg": widget._avg_from_display_series(new_display_data.get(key, [])),
            "segment_meta": segment_meta,
            "point_meta": point_meta,
            "has_presence": bool(any(old_mask) or any(new_mask)),
        }

    def _labels_for(display_data):
        if not display_data:
            return []
        for series_key in SERIES_KEYS:
            series = display_data.get(series_key) or []
            if not series:
                continue
            out = []
            for item in series:
                if isinstance(item, (list, tuple)) and len(item) >= 1:
                    out.append(str(item[0]).split(" - ")[0])
                else:
                    out.append("")
            return out
        return []

    old_range = _range_for_display_data(old_display_data, widget.visible_series)
    new_range = _range_for_display_data(new_display_data, widget.visible_series)

    return (
        old_series,
        new_series,
        sample_count,
        _labels_for(old_display_data),
        _labels_for(new_display_data),
        old_display_data,
        new_display_data,
        render_cache,
        old_range,
        new_range,
    )


def get_display_data_impl(widget):
    if widget._binned_data_cache is not None:
        return widget._binned_data_cache
    widget._binned_data_cache = widget._compute_display_data(widget.retention_data)
    return widget._binned_data_cache


def _mask_low_reviews(display_data, min_reviews):
    """Blank the rate of every point that has fewer than min_reviews reviews.

    The counts stay on the point, so the tooltip can still show them."""
    if min_reviews <= 0:
        return display_data
    masked = {}
    for key, series in display_data.items():
        out = []
        for item in series or []:
            if isinstance(item, (list, tuple)) and len(item) >= 3 and item[2]:
                try:
                    total = float(item[2][1] or 0)
                except Exception:
                    total = 0.0
                if 0 < total < min_reviews:
                    item = (item[0], None, item[2])
            out.append(item)
        masked[key] = out
    return masked


def series_totals_impl(widget):
    """{series: (passed, reviews)} over the zoomed window the chart shows."""
    data = widget.retention_data or {}
    # Asked several times per refresh for the same window: memoize on the series identity.
    token = tuple((id(data.get(k)), len(data.get(k) or ())) for k in SERIES_KEYS)
    cached = getattr(widget, "_series_totals_cache", None)
    if cached is not None and cached[0] == token and cached[1] is data:
        return dict(cached[2])
    totals = {}
    for key in SERIES_KEYS:
        passed = reviews = 0
        for item in data.get(key) or []:
            if isinstance(item, (list, tuple)) and len(item) >= 3 and item[2]:
                try:
                    passed += int(item[2][0] or 0)
                    reviews += int(item[2][1] or 0)
                except Exception:
                    log_swallowed()
        totals[key] = (passed, reviews)
    widget._series_totals_cache = (token, data, dict(totals))
    return totals


def set_min_reviews_impl(widget, value):
    try:
        value = max(0, int(value or 0))
    except Exception:
        value = 0
    if value == widget.min_reviews:
        return
    widget.min_reviews = value
    widget._invalidate_data_caches()
    widget._scaffold_cache_key = None
    widget._chrome_cache_key = None
    widget.update()


def _notify_totals(widget):
    try:
        widget.totals_changed.emit()
    except Exception:
        log_swallowed()


def compute_display_data_impl(widget, source_data):
    return _mask_low_reviews(_compute_display_data_unmasked(widget, source_data), int(getattr(widget, "min_reviews", 0) or 0))


def _compute_display_data_unmasked(widget, source_data):
    source_data = source_data or {}
    if not widget.binning_active:
        return source_data

    n = 0
    for key in SERIES_KEYS:
        if source_data.get(key):
            n = len(source_data[key])
            break

    bs = get_bin_size(n)
    if bs <= 1:
        return source_data

    binned_all = {}
    for key in SERIES_KEYS:
        data = source_data.get(key, [])
        if not data:
            binned_all[key] = []
            continue

        series_binned = []
        for i in range(0, len(data), bs):
            chunk = data[i : i + bs]
            total_passed = 0
            total_cards = 0
            sum_percent = 0
            count_percent = 0

            for item in chunk:
                if isinstance(item, (list, tuple)):
                    if len(item) >= 3 and item[2]:
                        passed, total = item[2]
                        total_passed += passed
                        total_cards += total
                    elif len(item) >= 2 and item[1] is not None:
                        sum_percent += item[1]
                        count_percent += 1

            if total_cards > 0:
                new_percent = (total_passed / total_cards) * 100
            elif count_percent > 0:
                new_percent = sum_percent / count_percent
            else:
                new_percent = None

            first_label = str(chunk[0][0]) if isinstance(chunk[0], (list, tuple)) else ""
            last_label = str(chunk[-1][0]) if isinstance(chunk[-1], (list, tuple)) else ""
            if first_label and last_label and first_label != last_label:
                label = f"{first_label} - {last_label}"
            else:
                label = first_label

            if total_cards > 0:
                series_binned.append((label, new_percent, (total_passed, total_cards)))
            else:
                series_binned.append((label, new_percent))

        binned_all[key] = series_binned
    return binned_all


def get_display_n_impl(widget):
    data = widget._get_display_data()
    for key in SERIES_KEYS:
        if data.get(key):
            return len(data[key])
    return 0


def invalidate_data_caches_impl(widget):
    widget._path_cache = {}
    widget._margin_cache = None
    widget._labels_cache = None
    widget._binned_data_cache = None
    widget._calc_averages()


def calc_averages_impl(widget):
    display_data = widget._get_display_data()
    for key in widget.SERIES_CONFIG:
        data = display_data.get(key, [])
        widget.avg_values[key] = widget._avg_from_series_rows(data, widget.avg_on_active_days)


def avg_from_series_rows_impl(widget, series_rows, active_only):
    vals = []
    for item in (series_rows or []):
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue

        val = item[1]
        val_f = None if val is None else float(val or 0.0)
        total_cards = None
        if len(item) >= 3 and item[2]:
            try:
                total_cards = float((item[2][1]) or 0.0)
            except Exception:
                total_cards = 0.0

        is_active = (total_cards is not None and total_cards > 0.0) or (
            total_cards is None and val_f is not None and val_f > 0.0
        )

        if active_only:
            if is_active and val_f is not None:
                vals.append(val_f)
        else:
            if is_active and val_f is not None:
                vals.append(val_f)
            else:
                vals.append(0.0)

    return (sum(vals) / len(vals)) if vals else None


def avg_from_display_series_impl(widget, data):
    return widget._avg_from_series_rows(data, widget.avg_on_active_days)


def get_series_avg_y_impl(widget, series_key, margin_top, plot_h, max_val, min_val=0):
    if not widget.visible_series.get(series_key, False):
        return None

    val_range = max(float(max_val) - float(min_val), 0.001)

    if widget._data_transition_active:
        transition_cache = (widget._data_transition_render_cache or {}).get(series_key, {})
        old_avg = transition_cache.get("old_avg")
        new_avg = transition_cache.get("new_avg")
        if old_avg is None and new_avg is None:
            return None
        if old_avg is None:
            old_avg = new_avg
        if new_avg is None:
            new_avg = old_avg
        p = max(0.0, min(1.0, float(widget.get_progress())))
        y_old = margin_top + plot_h - (max(0.0, (old_avg - min_val) / val_range) * plot_h)
        y_new = margin_top + plot_h - (max(0.0, (new_avg - min_val) / val_range) * plot_h)
        return y_old + ((y_new - y_old) * p)

    avg_val = widget.avg_values.get(series_key)
    if avg_val is None:
        return None
    return margin_top + plot_h - (max(0.0, (avg_val - min_val) / val_range) * plot_h)


def get_series_avg_alpha_impl(widget, series_key):
    if not widget.visible_series.get(series_key, False):
        return 0.0

    if widget._data_transition_active:
        transition_cache = (widget._data_transition_render_cache or {}).get(series_key, {})
        old_avg = transition_cache.get("old_avg")
        new_avg = transition_cache.get("new_avg")
        p = max(0.0, min(1.0, float(widget.get_progress())))
        old_visible = old_avg is not None
        new_visible = new_avg is not None
        if old_visible and new_visible:
            return 1.0
        if old_visible and not new_visible:
            return max(0.0, 1.0 - p)
        if (not old_visible) and new_visible:
            return p
        return 0.0

    avg_val = widget.avg_values.get(series_key)
    return 1.0 if avg_val is not None else 0.0


def set_series_visible_impl(widget, series_key, visible):
    if series_key in widget.visible_series:
        widget.visible_series[series_key] = visible
        if getattr(widget, "fit_to_data", False):
            widget._path_cache = {}
            widget._scaffold_cache_key = None
            widget._scaffold_cache_pixmap = None
        widget.update()


def get_margin_right_impl(widget, font_metrics):
    if not getattr(widget, "cumulative_visible", False):
        from .bars import axis_margin

        display_data = widget._get_display_data() or {}
        n = max((len(display_data.get(k) or []) for k in SERIES_KEYS), default=0)
        return max(8, axis_margin(widget, font_metrics, display_data, n))
    display_data = widget._get_display_data() or {}
    cumulative_steps = []
    for item in (display_data.get("all", []) or []):
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            continue
        payload = item[2]
        if not isinstance(payload, (list, tuple)) or len(payload) < 2:
            continue
        try:
            cumulative_steps.append(float(payload[1] or 0.0))
        except Exception:
            continue
    return ChartGeometry.calculate_dynamic_right_margin(font_metrics, cumulative_steps, True)


def apply_zoom_to_data_impl(widget):
    start, end = widget.get_zoom_range()
    widget.retention_data = {}
    for key, data in widget._full_retention_data.items():
        if data:
            widget.retention_data[key] = data[start:end]
        else:
            widget.retention_data[key] = []
    widget._path_cache = {}
    widget._margin_cache = None
    widget._labels_cache = None
    widget._binned_data_cache = None
    widget._calc_averages()
    _notify_totals(widget)
    widget.update()


def set_fit_to_data_impl(widget, enabled):
    widget.fit_to_data = bool(enabled)
    widget._path_cache = {}
    widget._scaffold_cache_key = None
    widget._scaffold_cache_pixmap = None
    widget._chrome_cache_key = None
    widget._chrome_cache_pixmap = None
    widget.update()


def current_value_range(widget):
    """(min, max) of the value axis as it is drawn right now.

    Fixed 0..100 normally; with "Within data limit" it is the data range, glided
    between the old and new range while a data transition runs. Painting and the
    hover code both read it so they place the lines identically."""
    if not getattr(widget, "fit_to_data", False):
        return 0.0, 100.0
    if getattr(widget, "_data_transition_active", False):
        p = max(0.0, min(1.0, float(getattr(widget, "_progress", 1.0))))
        old_min, old_max = getattr(widget, "_data_transition_old_range", (0.0, 100.0))
        new_min, new_max = getattr(widget, "_data_transition_new_range", (0.0, 100.0))
        return old_min + (new_min - old_min) * p, old_max + (new_max - old_max) * p
    return widget.get_data_range()


def get_data_range_impl(widget):
    """Returns (min_val, max_val) = exact data range for fit_to_data mode."""
    return _range_for_display_data(widget._get_display_data() or {}, widget.visible_series)


def get_stats_text_impl(widget):
    stats = []
    if getattr(widget, "avg_visible", True):
        for key in SERIES_KEYS:
            if widget.visible_series.get(key, False):
                val = widget._avg_from_series_rows((widget.retention_data or {}).get(key, []), widget.avg_on_active_days)
                if val is not None and val > 0:
                    lbl = widget.SERIES_CONFIG[key]["label"]
                    stats.append(f"{lbl} Avg: {fmt_num_compact(val)}%")
    return stats
