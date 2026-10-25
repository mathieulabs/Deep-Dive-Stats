# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from contextlib import contextmanager

from aqt.qt import QPoint, QWidget

from .motion import animations_enabled
from ...const import Config
from ..logic.logger import log_swallowed


DEFAULT_VISIBLE_ANIMATED_CHARTS = 6
MIN_VISIBLE_CHART_FRACTION = 0.8
SUPPRESS_CHART_ANIMATIONS_PROPERTY = "deepdivestats_suppress_chart_animations"
_ACTIVE_CHART_ANIMATION_BATCHES = {}
_CHART_ANIMATION_BATCH_SEQ = 0


def _chart_animations_temporarily_suppressed(widget):
    current = widget if isinstance(widget, QWidget) else None
    seen = set()
    while current is not None:
        cid = id(current)
        if cid in seen:
            break
        seen.add(cid)
        try:
            if bool(current.property(SUPPRESS_CHART_ANIMATIONS_PROPERTY)):
                return True
        except Exception:
            log_swallowed()
        try:
            current = current.parentWidget()
        except Exception:
            break
    return False


def _resolve_chart_root(widget):
    if widget is None or not isinstance(widget, QWidget):
        return None
    try:
        return widget.window() or widget
    except Exception:
        return widget


def chart_visible_fraction(widget, root=None):
    if widget is None or not isinstance(widget, QWidget):
        return 0.0
    if widget.width() <= 0 or widget.height() <= 0:
        return 0.0
    if root is None:
        try:
            root = widget.window() or widget
        except Exception:
            root = widget
    try:
        if not widget.isVisibleTo(root):
            return 0.0
    except Exception:
        if widget.isHidden():
            return 0.0
    try:
        region = widget.visibleRegion()
        if root.isVisible() and region.isEmpty():
            return 0.0
        visible_rect = region.boundingRect()
        visible_area = max(0, int(visible_rect.width())) * max(0, int(visible_rect.height()))
        total_area = max(1, int(widget.width()) * int(widget.height()))
        return max(0.0, min(1.0, float(visible_area) / float(total_area)))
    except Exception:
        return 1.0


def _chart_has_animation_work(widget):
    if widget is None or not isinstance(widget, QWidget):
        return False
    checker = getattr(widget, "_has_meaningful_data_for_animation", None)
    if callable(checker):
        try:
            return bool(checker())
        except Exception:
            return True
    return True


def _collect_chart_animation_targets(widget):
    if widget is None or not isinstance(widget, QWidget):
        return []

    targets = []
    seen = set()

    def _add_target(candidate):
        if candidate is None or not isinstance(candidate, QWidget):
            return
        if not bool(getattr(candidate, "_is_chart_anim_target", False)):
            return
        cid = id(candidate)
        if cid in seen:
            return
        seen.add(cid)
        targets.append(candidate)

    _add_target(widget)

    direct_body = getattr(widget, "body_widget", None)
    if isinstance(direct_body, QWidget):
        _add_target(direct_body)
        for candidate in direct_body.findChildren(QWidget):
            _add_target(candidate)

    for candidate in widget.findChildren(QWidget):
        _add_target(candidate)

    return targets


def normalize_chart_animation_target(widget):
    targets = _collect_chart_animation_targets(widget)
    return targets[0] if targets else None


def collect_chart_animation_targets(widget):
    return list(_collect_chart_animation_targets(widget))


def _active_chart_animation_batch(widget):
    root = _resolve_chart_root(widget)
    if root is None:
        return None
    batch = _ACTIVE_CHART_ANIMATION_BATCHES.get(id(root))
    if batch and batch.get("root") is root:
        return batch
    if batch is not None:
        _ACTIVE_CHART_ANIMATION_BATCHES.pop(id(root), None)
    return None


def _visible_batch_target_count(root, targets):
    count = 0
    for target in targets:
        if target is None or not isinstance(target, QWidget):
            continue
        if not _chart_has_animation_work(target):
            continue
        if chart_visible_fraction(target, root) >= MIN_VISIBLE_CHART_FRACTION:
            count += 1
    return count


def _next_chart_animation_batch_key():
    global _CHART_ANIMATION_BATCH_SEQ
    _CHART_ANIMATION_BATCH_SEQ += 1
    return int(_CHART_ANIMATION_BATCH_SEQ)


def _target_row_geometry(root, target):
    try:
        if target is None or not isinstance(target, QWidget):
            return None
        if not target.isVisible():
            return None
        if target.width() <= 0 or target.height() <= 0:
            return None
        top_left = target.mapTo(root, QPoint(0, 0))
        top = int(top_left.y())
        height = int(target.height())
        return top, max(1, height)
    except Exception:
        return None


def _group_targets_into_visual_rows(root, targets):
    rows = []
    last_row_top = None
    last_row_height = None

    for target in targets:
        geom = _target_row_geometry(root, target)
        if geom is None:
            rows.append([target])
            last_row_top = None
            last_row_height = None
            continue
        top, height = geom
        if not rows or last_row_top is None:
            rows.append([target])
            last_row_top = top
            last_row_height = height
            continue
        tolerance = max(18, int(min(last_row_height, height) * 0.45))
        if abs(int(top) - int(last_row_top)) <= tolerance:
            rows[-1].append(target)
            last_row_height = max(int(last_row_height), int(height))
        else:
            rows.append([target])
            last_row_top = top
            last_row_height = height
    return rows


def _build_queue_waves(root, targets, threshold, *, split_large_rows=True):
    rows = _group_targets_into_visual_rows(root, targets)
    wave_by_target_id = {}
    wave_target_counts = {}
    wave_index = 0
    large_row_min_targets = 3
    large_row_wave_max_targets = 2 if split_large_rows else 0
    small_row_max_rows = 3
    small_row_max_targets = max(1, min(int(threshold), 4))

    row_index = 0
    while row_index < len(rows):
        row_targets = list(rows[row_index])
        row_size = len(row_targets)

        if row_size >= large_row_min_targets:
            if large_row_wave_max_targets <= 0 or row_size <= large_row_wave_max_targets:
                for target in row_targets:
                    wave_by_target_id[id(target)] = wave_index
                wave_target_counts[wave_index] = len(row_targets)
                wave_index += 1
            else:
                start = 0
                while start < row_size:
                    chunk = row_targets[start:start + large_row_wave_max_targets]
                    for target in chunk:
                        wave_by_target_id[id(target)] = wave_index
                    wave_target_counts[wave_index] = len(chunk)
                    wave_index += 1
                    start += len(chunk)
            row_index += 1
            continue

        current_wave_targets = list(row_targets)
        current_wave_rows = [row_index]
        next_row_index = row_index + 1
        while next_row_index < len(rows):
            next_row_targets = list(rows[next_row_index])
            next_row_size = len(next_row_targets)
            if next_row_size >= large_row_min_targets:
                break
            if len(current_wave_rows) >= small_row_max_rows:
                break
            if len(current_wave_targets) + next_row_size > small_row_max_targets:
                break
            current_wave_targets.extend(next_row_targets)
            current_wave_rows.append(next_row_index)
            next_row_index += 1

        for target in current_wave_targets:
            wave_by_target_id[id(target)] = wave_index
        wave_target_counts[wave_index] = len(current_wave_targets)
        wave_index += 1
        row_index = next_row_index

    return wave_by_target_id, wave_target_counts


@contextmanager
def chart_animation_batch(
    anchor_widget,
    candidates,
    *,
    threshold=None,
    force_repaint_candidates=False,
    queue_mode=False,
    split_large_rows=True,
):
    root = _resolve_chart_root(anchor_widget)
    if root is None:
        yield {
            "allowed": True,
            "candidate_ids": set(),
            "visible_count": 0,
            "threshold": 0,
            "queue_mode": False,
            "over_budget": False,
            "max_concurrent": 0,
        }
        return

    if threshold is None:
        threshold = get_chart_animation_visible_threshold()

    normalized_targets = []
    seen = set()
    for candidate in candidates or []:
        for target in _collect_chart_animation_targets(candidate):
            tid = id(target)
            if tid in seen:
                continue
            seen.add(tid)
            normalized_targets.append(target)

    visible_count = _visible_batch_target_count(root, normalized_targets)
    over_budget = bool(visible_count > int(threshold))
    batch_key = _next_chart_animation_batch_key()
    candidate_order_map = {id(target): idx for idx, target in enumerate(normalized_targets)}
    if queue_mode:
        visible_queue_targets = [
            target
            for target in normalized_targets
            if _chart_has_animation_work(target)
            and chart_visible_fraction(target, root) >= MIN_VISIBLE_CHART_FRACTION
        ]
        wave_by_target_id, wave_target_counts = _build_queue_waves(
            root,
            visible_queue_targets,
            threshold,
            split_large_rows=split_large_rows,
        )
    else:
        wave_by_target_id, wave_target_counts = {}, {}
    batch = {
        "batch_key": batch_key,
        "root": root,
        "candidate_ids": {id(target) for target in normalized_targets},
        "candidate_order_map": candidate_order_map,
        "force_repaint_candidate_ids": (
            {id(target) for target in normalized_targets} if force_repaint_candidates else set()
        ),
        "visible_count": int(visible_count),
        "threshold": int(threshold),
        "queue_mode": bool(queue_mode),
        "over_budget": over_budget,
        "max_concurrent": max(1, int(threshold)),
        "allowed": bool(normalized_targets) if queue_mode else (not over_budget),
        "wave_by_target_id": wave_by_target_id,
        "wave_target_counts": wave_target_counts,
    }
    key = id(root)
    previous = _ACTIVE_CHART_ANIMATION_BATCHES.get(key)
    _ACTIVE_CHART_ANIMATION_BATCHES[key] = batch
    try:
        yield batch
    finally:
        if previous is None:
            _ACTIVE_CHART_ANIMATION_BATCHES.pop(key, None)
        else:
            _ACTIVE_CHART_ANIMATION_BATCHES[key] = previous


@contextmanager
def local_chart_animation_batch(anchor_widget, candidates=None):
    normalized_candidates = list(candidates or [anchor_widget])
    expanded_target_count = 0
    seen = set()
    for candidate in normalized_candidates:
        for target in _collect_chart_animation_targets(candidate):
            tid = id(target)
            if tid in seen:
                continue
            seen.add(tid)
            expanded_target_count += 1
    threshold = max(1, expanded_target_count)
    with chart_animation_batch(
        anchor_widget,
        normalized_candidates,
        threshold=threshold,
        force_repaint_candidates=True,
        queue_mode=False,
    ) as batch:
        yield batch


def chart_animation_queue_limit(widget):
    batch = _active_chart_animation_batch(widget)
    if batch is None or not bool(batch.get("queue_mode")):
        return 0
    target = normalize_chart_animation_target(widget)
    if target is None:
        return 0
    if id(target) not in batch.get("candidate_ids", set()):
        return 0
    return max(1, int(batch.get("max_concurrent", batch.get("threshold", 1)) or 1))


def chart_animation_queue_plan(widget):
    batch = _active_chart_animation_batch(widget)
    if batch is None or not bool(batch.get("queue_mode")):
        return None
    target = normalize_chart_animation_target(widget)
    if target is None:
        return None
    target_id = id(target)
    if target_id not in batch.get("candidate_ids", set()):
        return None
    wave_by_target_id = batch.get("wave_by_target_id", {}) or {}
    if target_id not in wave_by_target_id:
        return None
    wave_index = int(wave_by_target_id.get(target_id, 0))
    wave_target_counts = batch.get("wave_target_counts", {}) or {}
    return {
        "batch_key": int(batch.get("batch_key", 0) or 0),
        "wave_index": wave_index,
        "wave_size": int(wave_target_counts.get(wave_index, 1) or 1),
        "order_index": int((batch.get("candidate_order_map", {}) or {}).get(target_id, 0)),
        "threshold": int(batch.get("threshold", 1) or 1),
    }


def chart_animation_force_repaint_allowed(widget):
    if bool(getattr(widget, "_force_repaint_current_animation", False)):
        return True
    batch = _active_chart_animation_batch(widget)
    if batch is None:
        return False
    target = normalize_chart_animation_target(widget)
    if target is None:
        return False
    return id(target) in batch.get("force_repaint_candidate_ids", set())


def chart_animation_force_repaint_requested(widget):
    batch = _active_chart_animation_batch(widget)
    if batch is None:
        return False
    target = normalize_chart_animation_target(widget)
    if target is None:
        return False
    return id(target) in batch.get("force_repaint_candidate_ids", set())


def _is_chart_candidate(widget, root):
    target = normalize_chart_animation_target(widget)
    if target is None:
        return False
    if not _chart_has_animation_work(target):
        return False
    return chart_visible_fraction(target, root) >= MIN_VISIBLE_CHART_FRACTION


def visible_chart_count(widget):
    if widget is None:
        return 0

    try:
        root = widget.window() or widget
    except Exception:
        root = widget

    if not isinstance(root, QWidget):
        return 1 if _is_chart_candidate(widget, widget) else 0

    # Every chart's showEvent asks this and each answer walks the whole window
    # tree. The answer cannot change within one event-loop pass, so it is computed
    # once per window per pass and shared.
    cached = _VISIBLE_COUNT_CACHE.get(id(root))
    if cached is not None and cached[0] is root:
        return cached[1]

    count = _count_chart_candidates(root)
    _VISIBLE_COUNT_CACHE[id(root)] = (root, count)
    _schedule_visible_count_cache_clear()
    return count


def _count_chart_candidates(root):
    """Same count as calling _is_chart_candidate on every widget of the window, in one
    pass over the tree instead of one findChildren per widget (that took tens of ms on
    each zoom reset). The children of a widget follow it in findChildren order, so its
    first chart is the first chart before the end of its block."""
    order = []
    pos = {}
    for w in [root] + root.findChildren(QWidget):
        if id(w) not in pos:
            pos[id(w)] = len(order)
            order.append(w)
    n = len(order)
    end = [i + 1 for i in range(n)]
    for i in range(n - 1, 0, -1):
        p = order[i].parent()
        while p is not None and id(p) not in pos:
            p = p.parent()
        if p is not None:
            a = pos[id(p)]
            if end[i] > end[a]:
                end[a] = end[i]
    is_target = [bool(getattr(w, "_is_chart_anim_target", False)) for w in order]
    next_target = [n] * (n + 1)
    for i in range(n - 1, -1, -1):
        next_target[i] = i if is_target[i] else next_target[i + 1]

    def first_inside(i):
        j = next_target[i]
        return order[j] if j < end[i] else None

    good = {}
    count = 0
    for i, w in enumerate(order):
        if is_target[i]:
            target = w
        else:
            target = None
            body = getattr(w, "body_widget", None)
            if isinstance(body, QWidget):
                b = pos.get(id(body))
                target = first_inside(b) if b is not None else normalize_chart_animation_target(body)
            if target is None:
                target = first_inside(i)
        if target is None:
            continue
        ok = good.get(id(target))
        if ok is None:
            ok = _chart_has_animation_work(target) and chart_visible_fraction(target, root) >= MIN_VISIBLE_CHART_FRACTION
            good[id(target)] = ok
        if ok:
            count += 1
    return count


_VISIBLE_COUNT_CACHE = {}
_VISIBLE_COUNT_CLEAR_PENDING = [False]


def _clear_visible_count_cache():
    _VISIBLE_COUNT_CACHE.clear()
    _VISIBLE_COUNT_CLEAR_PENDING[0] = False


def _schedule_visible_count_cache_clear():
    if _VISIBLE_COUNT_CLEAR_PENDING[0]:
        return
    _VISIBLE_COUNT_CLEAR_PENDING[0] = True
    try:
        from aqt.qt import QTimer

        QTimer.singleShot(0, _clear_visible_count_cache)
    except Exception:
        _clear_visible_count_cache()

def get_chart_animation_visible_threshold(default=DEFAULT_VISIBLE_ANIMATED_CHARTS):
    try:
        from ...config import read_config_value
        raw = read_config_value(Config.CHART_ANIMATION_VISIBLE_THRESHOLD, default)
        return max(1, min(24, int(raw)))
    except Exception:
        return int(default)


def chart_animations_allowed(widget, *, max_visible_charts=None):
    if _chart_animations_temporarily_suppressed(widget):
        return False
    scope_getter = getattr(widget, "_animation_scope", None)
    scope = scope_getter() if callable(scope_getter) else "all"
    if not animations_enabled(scope):
        return False
    batch = _active_chart_animation_batch(widget)
    if batch is not None:
        target = normalize_chart_animation_target(widget)
        if target is None:
            return False
        return bool(batch.get("allowed")) and (id(target) in batch.get("candidate_ids", set()))
    if max_visible_charts is None:
        max_visible_charts = get_chart_animation_visible_threshold()
    return visible_chart_count(widget) <= int(max_visible_charts)
