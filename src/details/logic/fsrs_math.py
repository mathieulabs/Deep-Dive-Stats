# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""FSRS memory formulas shared by the stats code."""

# Decay used by FSRS 4.5 and 5. FSRS 6 stores the preset's own decay on each card.
DEFAULT_DECAY = 0.5
FSRS6_DEFAULT_DECAY = 0.1542  # a preset never optimized, with FSRS-6

# The FSRS versions whose formulas this add-on knows (4: FSRS-4.5). With another one (FSRS-7 has
# another forgetting curve) the charts that work out a recall show a note instead of numbers.
KNOWN_VERSIONS = (4, 5, 6)
# The charts that work out a recall themselves (the others read the memory states Anki stores).
CURVE_CHARTS = frozenset((
    "retrievability", "sxr_heatmap", "bw_matrix", "memorised", "fsrs_calibration", "forgetting_curve",
    "fsrs_fatigue", "leech_detector", "stability_increase",
))
_VERSION = []


def fsrs_version():
    """The FSRS version Anki runs, 4 to 6 (4: FSRS-4.5), or None when it cannot be told."""
    if not _VERSION:
        _VERSION.append(_read_version())
    return _VERSION[0]


def _read_version():
    # The newest preset parameter field Anki has: fsrs_params_4 / _5 / _6 (Anki 24.11 on), else
    # fsrs_weights: FSRS-4.5 from Anki 23.12 (23.10's version is not known for sure).
    try:
        from anki.deck_config_pb2 import DeckConfig

        names = DeckConfig.Config.DESCRIPTOR.fields_by_name
    except Exception:
        return None
    return version_of_fields(names, _point_version())


def version_of_fields(names, point_version):
    nums = [int(n[12:]) for n in names if n.startswith("fsrs_params_") and n[12:].isdigit()]
    if nums:
        return max(nums)
    if "fsrs_weights" in names and point_version >= 231200:
        return 4
    return None


def _point_version():
    try:
        from anki.utils import point_version

        return int(point_version())
    except Exception:
        return 0


def curve_known(version=None):
    """True when the forgetting curve of the FSRS version Anki runs is known here."""
    return (fsrs_version() if version is None else version) in KNOWN_VERSIONS


def preset_decay(params, version=None):
    """The decay of the forgetting curve for a preset's parameters, as Anki runs them, or None when
    unknown. FSRS-6: the last of its 21; 17 or 19 (FSRS-4.5, 5, run that way by FSRS-6 too): 0.5;
    none (never optimized): the default of the version Anki runs."""
    version = fsrs_version() if version is None else version
    if version not in KNOWN_VERSIONS:
        return None
    n = len(params or ())
    if n == 0:
        return FSRS6_DEFAULT_DECAY if version >= 6 else DEFAULT_DECAY
    if n in (17, 19):
        return DEFAULT_DECAY
    if n == 21 and version >= 6:
        try:
            decay = float(params[20])
        except (TypeError, ValueError):
            return None
        return decay if decay > 0 else None
    return None


def retrievability(elapsed_days, stability, decay=None):
    """Chance of recalling a card `elapsed_days` after its last review, as 0..1."""
    if not stability or stability <= 0:
        return 0.0
    try:
        decay = float(decay) if decay else DEFAULT_DECAY
    except (TypeError, ValueError):
        decay = DEFAULT_DECAY
    if decay <= 0:
        decay = DEFAULT_DECAY
    factor = 0.9 ** (-1.0 / decay) - 1.0
    return (1.0 + factor * max(0.0, elapsed_days) / stability) ** (-decay)


# The cards of the FSRS charts (Stability, Difficulty, Retrievability), counted as in
# Anki's own graphs (rslib stats/graphs): every card with a memory state, suspended and
# buried ones included. Select FSRS_CARD_COLS from "cards AS cards" where FSRS_CARD_COND.
FSRS_CARD_COLS = "cards.data, cards.due, cards.odue, cards.odid, cards.ivl, cards.queue, cards.type"
FSRS_CARD_COND = "cards.data IS NOT NULL AND cards.data != ''"


def memory_state(data):
    """(stability, difficulty 1-10, decay, last review time in seconds or None) of a card's
    data, or None when it has no FSRS memory state."""
    if not data:
        return None
    if isinstance(data, bytes):
        try:
            from anki.cards_pb2 import CardData

            cd = CardData.FromString(data)
            if cd.HasField("fsrs"):
                return float(cd.fsrs.stability), float(cd.fsrs.difficulty), None, None
        except Exception:
            pass
        return None
    if not isinstance(data, str):
        return None
    try:
        import json

        jd = json.loads(data)
        if isinstance(jd, dict) and not ("s" in jd and "d" in jd) and "cd" in jd:
            jd = json.loads(jd["cd"]) if isinstance(jd["cd"], str) else jd["cd"]
        if not isinstance(jd, dict) or jd.get("s") is None or jd.get("d") is None:
            return None
        return float(jd["s"]), float(jd["d"]), jd.get("decay"), jd.get("lrt")
    except Exception:
        return None


def _percent_bin(x):
    """Anki's percent_to_bin(x, 1): 0..99, 100 going in the last bin."""
    return max(0, min(99, int(x // 1)))


def seconds_since_last_review(lrt, due, odue, odid, ivl, queue, ctype, today, now):
    """Anki's seconds_since_last_review: from the stored last review time, else from the
    due day and interval (not exact after "set due date"), else from a learning due."""
    due = odue if odid else due
    try:
        lrt = int(lrt) if lrt else 0
    except (TypeError, ValueError):
        lrt = 0
    if lrt > 0:
        elapsed = now - lrt
    elif (ctype != 0 and due <= 365000) or queue in (2, 3) or (ctype == 2 and queue < 0):
        elapsed = (today - due + (ivl or 0)) * 86400
    else:
        elapsed = now - due
    return max(0, elapsed)


def add_memory_state(buckets, mem, due, odue, odid, ivl, queue, ctype, today, now):
    """Count one card in buckets {"stability", "difficulty", "retrievability"} as Anki does:
    stability rounded to whole days (100 = 100 or more here), difficulty and retrievability
    in 1% bins; the time since the last review from the stored review time, else from the
    due day and interval (Anki's seconds_since_last_review)."""
    s, d, decay, lrt = mem
    s_b = min(int(s + 0.5), 100) if s > 0 else 0
    buckets["stability"][s_b] = buckets["stability"].get(s_b, 0) + 1
    d_b = _percent_bin((d - 1.0) / 9.0 * 100.0)
    buckets["difficulty"][d_b] = buckets["difficulty"].get(d_b, 0) + 1

    if not curve_known():
        return  # no retrievability: an unknown curve would give wrong ones
    elapsed = seconds_since_last_review(lrt, due, odue, odid, ivl, queue, ctype, today, now)
    r = retrievability(elapsed / 86400.0, s, decay)
    r_b = _percent_bin(r * 100.0)
    buckets["retrievability"][r_b] = buckets["retrievability"].get(r_b, 0) + 1
