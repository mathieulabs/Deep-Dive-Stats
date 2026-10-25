# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from contextlib import contextmanager
from aqt.qt import QLabel
from ...chart_utils.zoom_mixin import preserve_zoom
from .styler import apply_style
from .wrapper import _wrap
from .utils import _addon_config

from .builders.activity import _build_activity
from .builders.retention import _build_retention
from .builders.added import _build_added
from .builders.distribution import _build_distribution
from .builders.card_counts import _build_card_counts
from .builders.heatmap import _build_heatmap
from .builders.hourly import _build_hourly
from .builders.future_due import _build_future_due
from .builders.review_intervals import _build_review_intervals
from .builders.stability import _build_stability
from .builders.difficulty import _build_difficulty
from .builders.retrievability import _build_retrievability
from .builders.text_label import _build_text_label
from .....qss import set_qss


@contextmanager
def _keep_chart_zoom(inner, widget_def, deck_id=None):
    """Keep the zoom of pinned charts across an in-place refresh (deck change, new data).

    It is dropped when the user picks another time span or the row count changes,
    since the old window no longer means the same thing. It is also dropped when the
    deck changes: keeping it there showed the zoom resetting for an instant, so a
    deck change now resets the zoom cleanly.
    """
    charts = []
    try:
        from aqt.qt import QWidget
        cands = [inner] + list(inner.findChildren(QWidget))
        charts = [c for c in cands if getattr(c, "_zoom_signals", None) is not None]
    except Exception:
        charts = []
    token = (widget_def.get("time_span"), widget_def.get("custom_days"), widget_def.get("_timespan_token"), str(deck_id))
    keep = []
    for c in charts:
        if getattr(c, "_pinned_zoom_token", token) == token:
            keep.append(c)
        c._pinned_zoom_token = token
    with preserve_zoom(*keep, notify=True):
        yield


def _resolve_deck_ids(deck_ids, context_deck_id):
    """Turn a widget's deck_ids into the deck id used to fetch data.

    deck_ids:
      None  -> all decks, following the context deck
      []    -> all standard decks (no deleted)
      list  -> explicit int deck ids and/or "deleted"

    If the context deck is in the explicit selection, the widget shows just that
    deck.
    """
    if deck_ids is None or deck_ids == []:
        return context_deck_id

    numeric_ids = [d for d in deck_ids if isinstance(d, int)]
    include_deleted = "deleted" in deck_ids

    if include_deleted and not numeric_ids:
        return -1

    if context_deck_id and isinstance(context_deck_id, int) and context_deck_id in numeric_ids:
        return context_deck_id

    return deck_ids


class WidgetFactory:
    """Creates a self-contained QWidget for a pinned widget definition."""

    @staticmethod
    def create(widget_def, deck_id=None, cache=None, parent=None, cfg=None):
        wtype = widget_def.get("type", "")
        default_labels = {
            "activity": "Activity",
            "retention": "Retention",
            "heatmap": "Heatmap",
            "added": "Added",
            "distribution": "Distribution",
            "card_counts": "Card Counts",
            "hourly": "Hourly Breakdown",
            "future_due": "Future Due",
            "review_intervals": "Review Intervals",
            "stability": "Card Stability",
            "difficulty": "Card Difficulty",
            "retrievability": "Card Retrievability",
            "text_label": "Text Widget",
        }
        label = widget_def.get("label") or default_labels.get(wtype, wtype.replace("_", " ").title())
        if wtype != "stat_card" and widget_def.get("label") is not None and not str(widget_def.get("label")).strip():
            label = None  # emptied title: no header
        if wtype == "text_label":
            label = None

        if "deck_ids" in widget_def:
            deck_id = _resolve_deck_ids(widget_def["deck_ids"], deck_id)
        elif "deck_id" in widget_def:
            deck_id = widget_def["deck_id"]

        from .builders.stat_card import _build_stat_card
        builders = {
            "activity": _build_activity,
            "retention": _build_retention,
            "added": _build_added,
            "distribution": _build_distribution,
            "card_counts": _build_card_counts,
            "heatmap": _build_heatmap,
            "stat_card": _build_stat_card,
            "hourly": _build_hourly,
            "future_due": _build_future_due,
            "review_intervals": _build_review_intervals,
            "stability": _build_stability,
            "difficulty": _build_difficulty,
            "retrievability": _build_retrievability,
            "text_label": _build_text_label,
        }

        builder = builders.get(wtype)
        if not builder:
            return None

        try:
            inner = builder(widget_def, deck_id, cache=cache, parent=parent, cfg=cfg)
            if inner is None:
                return None
            from ...chart_utils.browser_click import set_pinned_deck
            set_pinned_deck(inner, deck_id)

            if wtype == "stat_card":
                return inner

            if inner.objectName() == "pinned_widget_card":
                return inner

            color = getattr(inner, "color", None)
            if color is None and hasattr(inner, "base_color"):
                 color = inner.base_color

            wrapped = _wrap(inner, label, base_color=color, wtype=wtype, widget_id=widget_def.get("id"), saved_w=widget_def.get("width"), saved_h=widget_def.get("height"), parent=parent)
            return wrapped
        except Exception as e:
            l = QLabel(f"Error: {e}")
            set_qss(l, "color: red; font-weight: bold;")
            return l

    @staticmethod
    def update(wrapper, widget_def, deck_id=None, cache=None, fail_if_not_cached=False, cfg=None):
        """Update an existing widget wrapper with new data."""
        if not wrapper:
            return False

        inner = getattr(wrapper, "inner_widget", None)
        if not inner:
            from ...stats_cards import StatCardWidget
            if isinstance(wrapper, StatCardWidget):
                inner = wrapper
            else:
                return False

        from ...stats_cards import StatCardWidget
        if wrapper.objectName() != "pinned_widget_card" and not isinstance(wrapper, StatCardWidget):
            return False

        wtype = widget_def.get("type", "")

        from .builders.activity import _update_activity
        from .builders.retention import _update_retention
        from .builders.added import _update_added
        from .builders.distribution import _update_distribution
        from .builders.card_counts import _update_card_counts
        from .builders.heatmap import _update_heatmap
        from .builders.stat_card import _update_stat_card
        from .builders.hourly import _update_hourly
        from .builders.future_due import _update_future_due
        from .builders.review_intervals import _update_review_intervals
        from .builders.stability import _update_stability
        from .builders.difficulty import _update_difficulty
        from .builders.retrievability import _update_retrievability
        from .builders.text_label import _update_text_label

        updaters = {
            "activity": _update_activity,
            "retention": _update_retention,
            "added": _update_added,
            "distribution": _update_distribution,
            "card_counts": _update_card_counts,
            "heatmap": _update_heatmap,
            "stat_card": _update_stat_card,
            "hourly": _update_hourly,
            "future_due": _update_future_due,
            "review_intervals": _update_review_intervals,
            "stability": _update_stability,
            "difficulty": _update_difficulty,
            "retrievability": _update_retrievability,
            "text_label": _update_text_label,
        }

        updater = updaters.get(wtype)
        if not updater:
            return False

        if "deck_ids" in widget_def:
            deck_id = _resolve_deck_ids(widget_def["deck_ids"], deck_id)
        elif "deck_id" in widget_def:
            deck_id = widget_def["deck_id"]

        try:
            from ...chart_utils.browser_click import set_pinned_deck
            set_pinned_deck(inner, deck_id)
            from ..zoom_link import held as _zoom_link_held

            with _zoom_link_held(), _keep_chart_zoom(inner, widget_def, deck_id):
                success = updater(inner, widget_def, deck_id, cache=cache, fail_if_not_cached=fail_if_not_cached, cfg=cfg)
            if success:
                if wrapper.objectName() == "pinned_widget_card" and hasattr(wrapper, "apply_size"):
                    wrapper.apply_size(widget_def.get("width"), widget_def.get("height"))

                from ...stats_cards import StatCardWidget
                label = widget_def.get("label")
                if label is not None and not isinstance(wrapper, StatCardWidget) and not str(label).strip():
                    # Emptied chart title: keep it hidden (no fallback to the default name).
                    header = wrapper.findChild(QLabel, "pinned_header")
                    if header:
                        header.setVisible(False)
                    label = None
                if label is not None:
                    if not label:
                        default_labels = {
                            "activity": "Activity", "retention": "Retention", "heatmap": "Heatmap",
                            "added": "Added", "distribution": "Distribution", "card_counts": "Card Counts",
                            "hourly": "Hourly Breakdown", "future_due": "Future Due",
                            "review_intervals": "Review Intervals", "stability": "Card Stability",
                            "text_label": "Text Widget",
                            "difficulty": "Card Difficulty", "retrievability": "Card Retrievability"
                        }
                        label = default_labels.get(wtype, wtype.replace("_", " ").title())

                    if isinstance(wrapper, StatCardWidget):
                        wrapper.update_val(wrapper.shown_value(), title=label, refresh=False)
                    else:
                        header = wrapper.findChild(QLabel, "pinned_header")
                        if header:
                            header.setText(label.upper())
                            if wtype != "heatmap":
                                header.setVisible(True)

            return success
        except Exception:
            return False

    @staticmethod
    def apply_style(card, base_color=None, config_manager=None, inner_widget=None):
        apply_style(card, base_color, config_manager, inner_widget)

    @staticmethod
    def _addon_config():
        return _addon_config()



