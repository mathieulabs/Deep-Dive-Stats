# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

"""Every box of pinned widgets is one line.

A box used to hold several lines (each widget's "row_num"). On screen a line of a box and
a box of one line look the same, so there are only lines now: each line of a box becomes
a box of its own, right where it was, with the same space above and under it. Done once,
the first time the pinned widgets are built with such a box (nothing changes on screen).
"""

from .imports import Config
from .block_order import (
    charts_section_key, normalize_block_order, stats_section_key, texts_section_key,
)
from ....logic.logger import log_swallowed

_KEY = {"stat": stats_section_key, "chart": charts_section_key, "text": texts_section_key}
_KIND = {"stat": "stats", "chart": "charts", "text": "texts"}
_BOX_FIELD = {"stat": "stat_box", "chart": "chart_box", "text": "text_box"}
# The space between two lines of a box before (stat cards: their rows' spacing; graphs and
# texts: CHART_SPACING).
_OLD_LINE_SPACE = {"stat": 4, "chart": 10, "text": 10}


def _nonneg(value):
    try:
        return max(0, int(value or 0))
    except Exception:
        return 0


def _family(d):
    t = d.get("type")
    return "stat" if t == "stat_card" else "text" if t == "text_label" else "chart"


def _box(d):
    fam = _family(d)
    if fam == "text":
        return _nonneg(d.get("text_box", d.get("chart_box", 0)))
    return _nonneg(d.get(_BOX_FIELD[fam], 0))


def split_config(cfg):
    """Turn the lines of every box into boxes of their own, in cfg (a settings dict).
    Returns True if something changed."""
    pins = list(cfg.get(Config.PINNED_WIDGETS) or [])
    if not any(_nonneg(d.get("row_num")) > 0 for d in pins if isinstance(d, dict)):
        return False
    pins = [dict(d) for d in pins if isinstance(d, dict)]
    used = {fam: {_box(d) for d in pins if _family(d) == fam} for fam in _KEY}
    order = normalize_block_order(
        cfg.get(Config.PINNED_BLOCK_ORDER),
        stats_boxes=sorted(used["stat"]),
        chart_boxes=sorted(used["chart"]),
        text_boxes=sorted(used["text"]),
    )
    gaps = dict(cfg.get(Config.PINNED_GAPS) or {})
    mapping = {}
    for fam, key_fn in _KEY.items():
        for box in sorted(used[fam]):
            rows = sorted({_nonneg(d.get("row_num")) for d in pins if _family(d) == fam and _box(d) == box})
            if rows == [0]:
                continue
            new = []
            for i, row in enumerate(rows):
                nb = box if i == 0 else max(used[fam]) + 1
                used[fam].add(nb)
                mapping[(fam, box, row)] = nb
                new.append((row, nb))
            old_key = key_fn(box)
            keys = [key_fn(nb) for _row, nb in new]
            if old_key in order:
                at = order.index(old_key)
                order[at:at + 1] = keys
            else:
                order += keys
            # The spaces: the one under a line is now the one under its box; the one under
            # the whole box, under its last line.
            under_box = gaps.pop("box:" + old_key, None)
            for i, (row, nb) in enumerate(new):
                value = gaps.pop(f"line:{_KIND[fam]}:{box}:{row}", None)
                if value is None and i < len(new) - 1:
                    # The space the lines of a box had (now the space between two boxes,
                    # which by default follows another setting): kept as it was on screen.
                    value = _OLD_LINE_SPACE[fam]
                if value is not None:
                    gaps["box:" + key_fn(nb)] = value
            if under_box is not None:
                gaps["box:" + keys[-1]] = under_box
    for d in pins:
        fam = _family(d)
        nb = mapping.get((fam, _box(d), _nonneg(d.get("row_num"))))
        if nb is not None:
            d[_BOX_FIELD[fam]] = nb
            if fam == "text":
                d.pop("chart_box", None)
        d.pop("row_num", None)
    cfg[Config.PINNED_WIDGETS] = pins
    cfg[Config.PINNED_BLOCK_ORDER] = order
    cfg[Config.PINNED_GAPS] = gaps
    return True


def split_lines_into_boxes():
    """Apply split_config to the saved settings, once (a no-op when already done)."""
    try:
        from ..store.registry import WidgetRegistry

        cfg = WidgetRegistry._config()
        if split_config(cfg):
            WidgetRegistry._write(cfg)
            return True
    except Exception:
        log_swallowed()
    return False
