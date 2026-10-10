# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
CARD_COUNT_TOTAL_KEYS = (
    "new",
    "learn",
    "relearn",
    "young",
    "mature",
    "suspended",
    "buried",
    "deleted",
)


def empty_distribution_payload():
    return {
        "learning": [0, 0, 0, 0],
        "young": [0, 0, 0, 0],
        "mature": [0, 0, 0, 0],
    }


def empty_card_counts_payload():
    payload = {key: 0 for key in CARD_COUNT_TOTAL_KEYS}
    payload["total"] = 0
    return payload


def empty_fsrs_payload():
    return {"stability": {}, "difficulty": {}, "retrievability": {}}


def get_context_payload(context, key):
    if isinstance(context, dict):
        return context.get(key)
    return None


def resolve_added_history_desc(context=None, is_skeleton=False, fetcher=None):
    added = get_context_payload(context, "added")
    if added is not None:
        return list(added)
    if is_skeleton:
        return []
    if callable(fetcher):
        return fetcher() or []
    return None


def has_distribution_values(data):
    return bool(data) and any(any(value != 0 for value in counts) for counts in data.values())


def resolve_distribution_payload(context=None, is_skeleton=False, fetcher=None):
    distribution = get_context_payload(context, "distribution")
    if distribution is not None:
        return distribution
    if is_skeleton:
        return empty_distribution_payload()
    if callable(fetcher):
        return fetcher() or {}
    return None


def normalize_card_counts(counts):
    if counts is None:
        return None
    if not isinstance(counts, dict):
        return {}

    normalized = dict(counts)
    if "total" not in normalized:
        normalized["total"] = sum(normalized.get(key, 0) for key in CARD_COUNT_TOTAL_KEYS)
    return normalized


def resolve_card_counts_payload(
    context=None,
    *,
    is_skeleton=False,
    fetcher=None,
    is_deleted=False,
    fetch_when_empty=True,
    fetch_when_non_deleted_zero_total=True,
):
    if is_skeleton:
        return empty_card_counts_payload()

    counts = normalize_card_counts(get_context_payload(context, "counts"))
    should_fetch = counts is None
    if counts == {} and fetch_when_empty:
        should_fetch = True
    if (
        not should_fetch
        and fetch_when_non_deleted_zero_total
        and not is_deleted
        and counts
        and counts.get("total", 0) <= 0
    ):
        should_fetch = True

    if should_fetch and callable(fetcher):
        counts = normalize_card_counts(fetcher() or {})

    return counts


def resolve_fsrs_payload(context=None, *, is_skeleton=False, fetcher=None, require_stability=False):
    fsrs = get_context_payload(context, "fsrs")
    if fsrs is not None:
        fsrs = fsrs or {}
        if (not require_stability) or bool(fsrs.get("stability")):
            return fsrs

    if is_skeleton:
        return empty_fsrs_payload()

    if callable(fetcher):
        return fetcher() or {}
    return None
