# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from .imports import Config

BLOCK_STATS = "stats"
BLOCK_CHARTS = "charts"
BLOCK_TEXTS = "texts"

DEFAULT_BLOCK_ORDER = [BLOCK_STATS, BLOCK_CHARTS, BLOCK_TEXTS]


def _to_nonneg_int(value, default=0):
    try:
        return max(0, int(value or 0))
    except Exception:
        return int(default)


def _ordered_unique_ints(values):
    out = []
    seen = set()
    for value in values or []:
        n = _to_nonneg_int(value, 0)
        if n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out


def stats_section_key(box_id):
    return f"{BLOCK_STATS}:{_to_nonneg_int(box_id, 0)}"


def charts_section_key(box_id):
    return f"{BLOCK_CHARTS}:{_to_nonneg_int(box_id, 0)}"


def texts_section_key(box_id):
    return f"{BLOCK_TEXTS}:{_to_nonneg_int(box_id, 0)}"


def parse_section_key(key):
    if key == BLOCK_STATS:
        return BLOCK_STATS, 0
    if key == BLOCK_CHARTS:
        return BLOCK_CHARTS, 0
    if key == BLOCK_TEXTS:
        return BLOCK_TEXTS, 0
    if not isinstance(key, str):
        return None, None
    if key.startswith(f"{BLOCK_STATS}:"):
        return BLOCK_STATS, _to_nonneg_int(key.split(":", 1)[1], 0)
    if key.startswith(f"{BLOCK_CHARTS}:"):
        return BLOCK_CHARTS, _to_nonneg_int(key.split(":", 1)[1], 0)
    if key.startswith(f"{BLOCK_TEXTS}:"):
        return BLOCK_TEXTS, _to_nonneg_int(key.split(":", 1)[1], 0)
    return None, None


def section_key_for_widget(widget_def):
    if not isinstance(widget_def, dict):
        return charts_section_key(0)
    wtype = widget_def.get("type")
    if wtype == "stat_card":
        return stats_section_key(widget_def.get("stat_box", 0))
    if wtype == "text_label":
        return texts_section_key(widget_def.get("text_box", widget_def.get("chart_box", 0)))
    return charts_section_key(widget_def.get("chart_box", 0))


def section_label(section_key):
    base, box_id = parse_section_key(section_key)
    if base == BLOCK_STATS:
        return "main stats section" if int(box_id or 0) == 0 else "stats section"
    if base == BLOCK_CHARTS:
        return "main charts section" if int(box_id or 0) == 0 else "charts section"
    if base == BLOCK_TEXTS:
        return "main text section" if int(box_id or 0) == 0 else "text section"
    return "section"


def normalize_block_order(raw_order, stats_boxes=None, chart_boxes=None, text_boxes=None):
    stats_boxes_list = _ordered_unique_ints(stats_boxes if stats_boxes is not None else [0])
    chart_boxes_list = _ordered_unique_ints(chart_boxes if chart_boxes is not None else [0])
    text_boxes_list = _ordered_unique_ints(text_boxes if text_boxes is not None else [])

    stats_keys = [stats_section_key(box_id) for box_id in stats_boxes_list]
    chart_keys = [charts_section_key(box_id) for box_id in chart_boxes_list]
    text_keys = [texts_section_key(box_id) for box_id in text_boxes_list]

    default_order = list(stats_keys)
    default_order.extend(text_keys)
    default_order.extend(chart_keys)

    allowed = set(default_order)
    order = []
    if isinstance(raw_order, list):
        for raw in raw_order:
            base, box_id = parse_section_key(raw)
            if base == BLOCK_STATS:
                key = stats_section_key(box_id or 0)
            elif base == BLOCK_CHARTS:
                key = charts_section_key(box_id or 0)
                if key not in allowed:
                    text_fallback = texts_section_key(box_id or 0)
                    if text_fallback in allowed:
                        key = text_fallback
            elif base == BLOCK_TEXTS:
                key = texts_section_key(box_id or 0)
                if key not in allowed:
                    chart_fallback = charts_section_key(box_id or 0)
                    if chart_fallback in allowed:
                        key = chart_fallback
            else:
                continue
            if key in allowed and key not in order:
                order.append(key)

    for key in default_order:
        if key not in order:
            order.append(key)
    return order


def block_for_widget(widget_def):
    return section_key_for_widget(widget_def)


def _strip_spacers(layout):
    while True:
        removed_any = False
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item is None:
                continue
            try:
                if item.spacerItem() is not None:
                    layout.takeAt(i)
                    removed_any = True
                    break
            except Exception:
                continue
        if not removed_any:
            break


def apply_block_layout_order(manager, pinned_conf, add_stretch=False):
    layout = getattr(manager, "_main_layout", None)
    overlay = getattr(manager, "_overlay", None)
    if layout is None or overlay is None:
        return []

    stats_containers = {}
    stats_map = getattr(manager, "_stats_containers", None)
    if isinstance(stats_map, dict) and stats_map:
        box_order = list(getattr(manager, "_stats_box_order", []) or [])
        for box_id in box_order:
            container = stats_map.get(box_id)
            if container is not None and not container.isHidden():
                stats_containers[_to_nonneg_int(box_id, 0)] = container
        for box_id, container in stats_map.items():
            if (
                container is not None
                and not container.isHidden()
                and _to_nonneg_int(box_id, 0) not in stats_containers
            ):
                stats_containers[_to_nonneg_int(box_id, 0)] = container
    else:
        stats_container = getattr(manager, "_stats_container", None)
        if stats_container is not None and not stats_container.isHidden():
            stats_containers[0] = stats_container

    charts_container = getattr(manager, "_charts_container", None)
    chart_containers = {}
    chart_boxes = getattr(manager, "_chart_boxes", None)
    if isinstance(chart_boxes, dict) and chart_boxes:
        box_order = list(getattr(manager, "_chart_box_order", []) or [])
        for box_id in box_order:
            box = chart_boxes.get(box_id) or {}
            container = box.get("container")
            if container is not None and not container.isHidden():
                chart_containers[_to_nonneg_int(box_id, 0)] = container
        for box_id, box in chart_boxes.items():
            container = box.get("container")
            if (
                container is not None
                and not container.isHidden()
                and _to_nonneg_int(box_id, 0) not in chart_containers
            ):
                chart_containers[_to_nonneg_int(box_id, 0)] = container
    elif charts_container is not None and not charts_container.isHidden():
        chart_containers[0] = charts_container

    texts_container = getattr(manager, "_texts_container", None)
    text_containers = {}
    text_boxes = getattr(manager, "_text_boxes", None)
    if isinstance(text_boxes, dict) and text_boxes:
        box_order = list(getattr(manager, "_text_box_order", []) or [])
        for box_id in box_order:
            box = text_boxes.get(box_id) or {}
            container = box.get("container")
            if container is not None and not container.isHidden():
                text_containers[_to_nonneg_int(box_id, 0)] = container
        for box_id, box in text_boxes.items():
            container = box.get("container")
            if (
                container is not None
                and not container.isHidden()
                and _to_nonneg_int(box_id, 0) not in text_containers
            ):
                text_containers[_to_nonneg_int(box_id, 0)] = container
    elif texts_container is not None and not texts_container.isHidden():
        text_containers[0] = texts_container


    raw_order = pinned_conf.get(Config.PINNED_BLOCK_ORDER, None)
    section_order = normalize_block_order(
        raw_order,
        stats_boxes=sorted(stats_containers.keys()),
        chart_boxes=sorted(chart_containers.keys()),
        text_boxes=sorted(text_containers.keys()),
    )

    section_to_widgets = {}
    for box_id, container in stats_containers.items():
        section_to_widgets[stats_section_key(box_id)] = [container]
    for box_id, container in chart_containers.items():
        section_to_widgets[charts_section_key(box_id)] = [container]
    for box_id, container in text_containers.items():
        section_to_widgets[texts_section_key(box_id)] = [container]

    ordered_sections = []
    ordered_widgets = []
    for section_id in section_order:
        widgets = section_to_widgets.get(section_id, [])
        if widgets:
            ordered_sections.append(section_id)
            ordered_widgets.extend(widgets)

    _strip_spacers(layout)

    stale_candidates = list(stats_containers.values())
    if isinstance(stats_map, dict):
        for container in stats_map.values():
            if container is not None and container not in stale_candidates:
                stale_candidates.append(container)
    if isinstance(chart_boxes, dict):
        for box in chart_boxes.values():
            container = box.get("container")
            if container is not None and container not in stale_candidates:
                stale_candidates.append(container)
    if isinstance(text_boxes, dict):
        for box in text_boxes.values():
            container = box.get("container")
            if container is not None and container not in stale_candidates:
                stale_candidates.append(container)
    if charts_container is not None and charts_container not in stale_candidates:
        stale_candidates.append(charts_container)
    if texts_container is not None and texts_container not in stale_candidates:
        stale_candidates.append(texts_container)

    for stale_widget in stale_candidates:
        if stale_widget is None:
            continue
        if stale_widget not in ordered_widgets and layout.indexOf(stale_widget) != -1:
            layout.removeWidget(stale_widget)

    for widget in ordered_widgets:
        if widget.parent() != overlay:
            widget.setParent(overlay)
        layout.removeWidget(widget)

    for idx, widget in enumerate(ordered_widgets):
        layout.insertWidget(idx, widget)

    if add_stretch and ordered_widgets:
        layout.addStretch(1)

    return ordered_sections
