# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""FSRS memory formulas shared by the stats code."""

# Decay used by FSRS 4.5 and 5. FSRS 6 stores the preset's own decay on each card.
DEFAULT_DECAY = 0.5


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
