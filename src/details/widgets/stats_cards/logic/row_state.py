# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from collections import defaultdict

from aqt import mw

from ....ui import Config, ConfigManager

ROW_NUM_DEFAULT = 0


def card_key(card):
    return getattr(card, "widget_id", None) or getattr(card, "config_key", None)


def normalize_row_nums(row_nums):
    out = {}
    for key, val in dict(row_nums or {}).items():
        if not key:
            continue
        try:
            n = int(val)
        except Exception:
            continue
        if n > ROW_NUM_DEFAULT:
            out[key] = n
    return out


def group_cards_by_row(cards, row_nums):
    groups_by_num = defaultdict(list)
    nums = normalize_row_nums(row_nums)
    for card in cards:
        key = card_key(card)
        num = nums.get(key, ROW_NUM_DEFAULT) if key else ROW_NUM_DEFAULT
        groups_by_num[num].append(card)
    return groups_by_num


def apply_saved_order(cards, ordered_keys):
    if not ordered_keys:
        return list(cards)
    rank = {k: i for i, k in enumerate(ordered_keys)}
    indexed = list(enumerate(cards))
    indexed.sort(key=lambda pair: (rank.get(card_key(pair[1]), len(rank) + pair[0])))
    return [card for _, card in indexed]


def collect_visible_unique_cards(rows):
    ordered = []
    seen = set()
    for row in rows:
        if not row.isVisible():
            continue
        for card in row.cards:
            if card not in seen:
                seen.add(card)
                ordered.append(card)
    return ordered


def _config_for_module(module_name):
    _ = module_name
    manager = ConfigManager(mw)
    return manager, dict(manager.config)


def persist_row_nums(row_nums, module_name):
    manager, cfg = _config_for_module(module_name)
    cfg[Config.DASH_STAT_ROW_NUMS] = normalize_row_nums(row_nums)
    manager.config = cfg
    manager.write_config()


def persist_dashboard_order(cards, module_name):
    manager, cfg = _config_for_module(module_name)
    cfg[Config.DASH_STAT_ORDER] = [k for c in cards if (k := card_key(c))]
    manager.config = cfg
    manager.write_config()

