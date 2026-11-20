# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The widget gallery's previews (gallery_web.py): a chart's data and options, a stat card's spec."""

from ..const import Period
from . import providers
from .trace import trace

# the periods a preview may outgrow when its chart is empty over them (chart_data)
_SHORT = (Period.TODAY, Period.YESTERDAY, Period.WEEK, Period.TWO_WEEKS, Period.MONTH, Period.THREE_MONTHS)
_YEARS = (Period.YEAR, Period.LAST_YEAR)


def chart_data(d, deck_id):
    """(data, options) of a chart's preview (any thread): as the pinned widget's "data" handler, over a longer period
    when it is empty over its own (a picture of nothing says nothing: no card introduced this month)."""
    from .pinned import _deck_of

    t = d.get("type")
    span = -1 if t == "heatmap" else int(d.get("time_span", -1))
    opts = providers.widget_options(t, own=d)
    deck = _deck_of(d, deck_id)
    data = providers.fetch(t, deck, span, opts, own=d)
    tries = (Period.YEAR, Period.TOTAL) if span in _SHORT else (Period.TOTAL,) if span in _YEARS else ()
    for longer in tries:
        if not providers.is_empty(t, data, deck, even_shown=True):
            break
        trace(f"GALLERY {t}: empty over its period, the preview shows a longer one ({longer})")
        data = providers.fetch(t, deck, longer, opts, own=d)
    opts = dict(opts or {})
    if t == "heatmap":
        opts["keep_color"] = True
    return data or {}, opts


def stat_card_spec(key, d, deck_id, size):
    """A stat card's spec for its preview (UI thread), filling size (w, h)."""
    from .pinned import stat_spec

    spec = stat_spec([(key, d)], deck_id)
    for c in spec.get("cards") or []:
        c["w"] = size[0]
    k = spec.setdefault("compact", {})
    # the pinned card's fonts are for its own height (about 50 px): in the taller preview they grow with it (the text
    # was small in the middle of the card), a little less than the height
    h0 = float(k.get("h") or size[1])
    f = max(1.0, min(1.45, size[1] / h0 * 0.9)) if h0 > 0 else 1.0
    for name in ("val", "title"):
        if k.get(name):
            k[name] = k[name] * f
    k["h"] = size[1]
    return spec
