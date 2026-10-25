# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ... import rollover_hour
from ..core.time_utils import custom_exact_date_bounds_from_ms


def build_collection_did_limit(excluded_dids):
    from .....utils import excluded_not_in_clause
    return excluded_not_in_clause(excluded_dids)


def resolve_prev_exact_bounds(prev_start_ms, prev_end_ms):
    return custom_exact_date_bounds_from_ms(prev_start_ms, prev_end_ms, rollover_hour())
