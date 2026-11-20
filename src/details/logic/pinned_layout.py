# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Where the pinned widgets sit on the main screen, and the moves that change it, without a window.

A widget is in a box of its family (graphs, texts, stat cards), on a line of that box (row_num), at a place in the
saved order of the widgets. The boxes are shown in the order PINNED_BLOCK_ORDER keeps ("stats:0", "charts:1"...).
The moves write the registry and the settings only: the caller redraws (the native overlay: its manager's refresh;
the web block: the config listener).
"""

from ...config import addon_config
from ...const import Config
from .widget_registry import WidgetRegistry

BLOCK_STATS = "stats"
BLOCK_CHARTS = "charts"
BLOCK_TEXTS = "texts"
BOX_KEY = {"stat": "stat_box", "chart": "chart_box", "text": "text_box"}


# ---- the boxes' keys and order ------------------------------------------------------------------------------------
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


KEY_FN = {"stat": stats_section_key, "chart": charts_section_key, "text": texts_section_key}


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


# ---- a widget's place -----------------------------------------------------------------------------------------------
def family(widget_def):
    wtype = widget_def.get("type")
    if wtype == "stat_card":
        return "stat"
    if wtype == "text_label":
        return "text"
    return "chart"


def box_of(widget_def):
    fam = family(widget_def)
    if fam == "text":
        return _to_nonneg_int(widget_def.get("text_box", widget_def.get("chart_box", 0)))
    return _to_nonneg_int(widget_def.get(BOX_KEY[fam], 0))


def row_of(widget_def):
    return _to_nonneg_int(widget_def.get("row_num", 0))


def box_value(fam, box):
    """The box as saved: texts keep 0, the other families save their first box as no key."""
    if fam == "text":
        return int(box)
    return None if int(box) == 0 else int(box)


def defs():
    return list(WidgetRegistry.get_all())


def find_def(widget_id):
    for d in WidgetRegistry.get_all():
        if d.get("id") == widget_id:
            return d
    return None


def section_order(widget_defs, config=None):
    """The boxes in the order they are shown (the saved order, completed with the boxes it lacks)."""
    conf = config if config is not None else (addon_config().config or {})
    return normalize_block_order(
        conf.get(Config.PINNED_BLOCK_ORDER, None),
        stats_boxes=sorted({box_of(d) for d in widget_defs if family(d) == "stat"}),
        chart_boxes=sorted({box_of(d) for d in widget_defs if family(d) == "chart"}),
        text_boxes=sorted({box_of(d) for d in widget_defs if family(d) == "text"}),
    )


def write_updates(updates_by_id):
    """Apply {widget_id: {key: value}} in one config write (None removes a key)."""
    if not updates_by_id:
        return
    cfg = WidgetRegistry._config()
    widgets = cfg.get(Config.PINNED_WIDGETS, [])
    for w in widgets:
        upd = updates_by_id.get(w.get("id"))
        if not upd:
            continue
        for key, value in upd.items():
            if value is None:
                w.pop(key, None)
            else:
                w[key] = value
    cfg[Config.PINNED_WIDGETS] = widgets
    WidgetRegistry._write(cfg)


# ---- the moves ------------------------------------------------------------------------------------------------------
def move_to(widget_id, box, row, anchor_id):
    """To another line or box of its family, in front of anchor_id there (or after the line's last widget).
    False when it was already there (nothing written)."""
    cur = find_def(widget_id)
    if cur is None:
        return False
    fam = family(cur)
    src_box, src_row = box_of(cur), row_of(cur)
    if (src_box, src_row) == (box, row):
        return False
    all_defs = defs()

    # A line left empty closes up, the lines after it move up by one.
    left = [d for d in all_defs if d.get("id") != widget_id and family(d) == fam and box_of(d) == src_box]
    if not any(row_of(d) == src_row for d in left):
        for d in left:
            r = row_of(d)
            if r > src_row:
                WidgetRegistry.update_settings_bulk(d["id"], {"row_num": (r - 1) or None})
        if src_box == box and row > src_row:
            row -= 1

    WidgetRegistry.update_settings_bulk(widget_id, {BOX_KEY[fam]: box_value(fam, box), "row_num": row or None, "col_offset": None})

    # Put it in the saved order right before the widget it lands in front of.
    ordered = [d["id"] for d in WidgetRegistry.get_all()]
    others = [i for i in ordered if i != widget_id]
    if anchor_id in others:
        pos = others.index(anchor_id)
    else:
        by_id = {d["id"]: d for d in WidgetRegistry.get_all()}
        mates = [
            i for i in others
            if family(by_id[i]) == fam and box_of(by_id[i]) == box and row_of(by_id[i]) == row
        ] or [i for i in others if family(by_id[i]) == fam and box_of(by_id[i]) == box]
        pos = others.index(mates[-1]) + 1 if mates else len(others)
    others.insert(pos, widget_id)
    WidgetRegistry.reorder(others)
    return True


def reorder(widget_id, anchor_id):
    """On its own line, in front of anchor_id (or after the last widget of its box). False when it is unknown."""
    all_defs = defs()
    cur = next((d for d in all_defs if d.get("id") == widget_id), None)
    if cur is None:
        return False
    fam, box = family(cur), box_of(cur)
    ids = [d["id"] for d in all_defs if d.get("id") != widget_id]
    if anchor_id in ids:
        ids.insert(ids.index(anchor_id), widget_id)
    else:
        mates = [d["id"] for d in all_defs if d.get("id") != widget_id and family(d) == fam and box_of(d) == box]
        ids.insert(ids.index(mates[-1]) + 1 if mates else len(ids), widget_id)
    WidgetRegistry.reorder(ids)
    return True


def place(widget_id, box, row, side, k):
    """At the start or the end of that line, then at its shift k there (the spot the outline showed).
    False when the widget is unknown."""
    all_defs = defs()
    cur = next((d for d in all_defs if d.get("id") == widget_id), None)
    if cur is None:
        return False
    fam = family(cur)
    mates = [d["id"] for d in all_defs if d.get("id") != widget_id and family(d) == fam
             and box_of(d) == box and row_of(d) == row]
    anchor = mates[0] if (side == "start" and mates) else None
    if (box_of(cur), row_of(cur)) != (box, row):
        move_to(widget_id, box, row, anchor)
    else:
        ids = [d["id"] for d in all_defs if d.get("id") != widget_id]
        if anchor is not None:
            ids.insert(ids.index(anchor), widget_id)
        elif mates:
            ids.insert(ids.index(mates[-1]) + 1, widget_id)
        else:
            ids.append(widget_id)
        WidgetRegistry.reorder(ids)
    write_updates({widget_id: {"col_offset": int(k) if k else None}})
    return True


def above(order, key):
    """The box right above key in order, or None."""
    if key in order and order.index(key) > 0:
        return order[order.index(key) - 1]
    return None


def fresh_gaps(keys, config=None):
    """The settings update that puts the spaces under these boxes back to the default: a box put somewhere new does
    not take a space changed by hand for what was there before."""
    keys = {"box:" + k for k in keys if k}
    conf = config if config is not None else (addon_config().config or {})
    gaps = dict(conf.get(Config.PINNED_GAPS) or {})
    if not any(k in gaps for k in keys):
        return {}
    return {Config.PINNED_GAPS: {k: v for k, v in gaps.items() if k not in keys}}


def rows_after_leaving(widget_defs, widget_id, fam):
    """Row numbers of the family's widgets once widget_id left its line: a line left empty closes up. ({id: (box,
    row)} for the others, (box, row) it left, whether that line was left empty)."""
    cur = next(d for d in widget_defs if d.get("id") == widget_id)
    sbox, srow = box_of(cur), row_of(cur)
    out = {}
    for d in widget_defs:
        if d.get("id") == widget_id or family(d) != fam:
            continue
        out[d["id"]] = (box_of(d), row_of(d))
    left_empty = not any(b == sbox and r == srow for b, r in out.values())
    if left_empty:
        for wid, (b, r) in list(out.items()):
            if b == sbox and r > srow:
                out[wid] = (b, r - 1)
    return out, (sbox, srow), left_empty


def write_rows(widget_defs, fam, rows, widget_id, box, row):
    updates = {}
    for d in widget_defs:
        wid = d.get("id")
        if wid in rows and rows[wid][1] != row_of(d):
            updates[wid] = {"row_num": rows[wid][1] or None}
    updates[widget_id] = {BOX_KEY[fam]: box_value(fam, box), "row_num": row or None, "col_offset": None}
    write_updates(updates)


def new_line(widget_id, box, row):
    """Alone on a new line at row of box (the lines from there move down). False when the widget is unknown."""
    all_defs = defs()
    cur = next((d for d in all_defs if d.get("id") == widget_id), None)
    if cur is None:
        return False
    fam = family(cur)
    rows, (sbox, srow), left_empty = rows_after_leaving(all_defs, widget_id, fam)
    if left_empty and sbox == box and row > srow:
        row -= 1
    for wid, (b, r) in list(rows.items()):
        if b == box and r >= row:
            rows[wid] = (b, r + 1)
    write_rows(all_defs, fam, rows, widget_id, box, row)
    return True


def new_box(widget_id, keys, index, cm=None):
    """Alone in a new box, shown at index among the boxes keys (as they were shown). False when it is unknown."""
    all_defs = defs()
    cur = next((d for d in all_defs if d.get("id") == widget_id), None)
    if cur is None:
        return False
    cm = cm or addon_config()
    fam = family(cur)
    used = [box_of(d) for d in all_defs if family(d) == fam]
    new_id = (max(used) + 1) if used else 1
    new_key = KEY_FN[fam](new_id)
    order = section_order(all_defs, cm.config or {})
    if index < len(keys) and keys[index] in order:
        order.insert(order.index(keys[index]), new_key)
    elif keys and keys[-1] in order:
        order.insert(order.index(keys[-1]) + 1, new_key)
    else:
        order.append(new_key)
    rows, _left, _empty = rows_after_leaving(all_defs, widget_id, fam)
    updates = {Config.PINNED_BLOCK_ORDER: order}
    updates.update(fresh_gaps([above(order, new_key), new_key], cm.config or {}))
    cm.write_config_vals(updates)
    write_rows(all_defs, fam, rows, widget_id, new_id, 0)
    return True


def move_box(key, keys, index, cm=None):
    """The box key put at index among the boxes shown (keys, as they were shown)."""
    cm = cm or addon_config()
    order = section_order(defs(), cm.config or {})
    rest = [k for k in keys if k != key]
    if key in keys and keys.index(key) < index:
        index -= 1
    old_above = above(order, key)
    order = [k for k in order if k != key]
    if index < len(rest) and rest[index] in order:
        order.insert(order.index(rest[index]), key)
    elif rest and rest[-1] in order:
        order.insert(order.index(rest[-1]) + 1, key)
    else:
        order.append(key)
    updates = {Config.PINNED_BLOCK_ORDER: order}
    updates.update(fresh_gaps([old_above, above(order, key), key], cm.config or {}))
    cm.write_config_vals(updates)
    return True


def apply(cross, cm=None):
    """A drop: {"kind": "move" | "reorder" | "newline" | "newbox" | "movebox" | "place", ...}. True when something
    may have changed (the caller redraws), False for an unknown kind or widget."""
    kind = cross.get("kind")
    if kind == "move":
        return move_to(cross["id"], int(cross.get("box") or 0), int(cross.get("row") or 0), cross.get("anchor"))
    if kind == "reorder":
        return reorder(cross["id"], cross.get("anchor"))
    if kind == "newline":
        return new_line(cross["id"], cross["box"], cross["row"])
    if kind == "newbox":
        return new_box(cross["id"], cross["keys"], cross["index"], cm)
    if kind == "movebox":
        return move_box(cross["id"], cross["keys"], cross["index"], cm)
    if kind == "place":
        return place(cross["id"], cross["box"], cross["row"], cross["side"], cross.get("k", 0))
    return False
