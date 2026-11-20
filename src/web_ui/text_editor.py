# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""What the web text editor (web/text_editor.js, the web TextLabelEditor) needs from Python: the variables, time
spans, units and decks it completes, and its help, already translated. No window: a page's 'te_data' handler
answers with editor_data().
"""

from __future__ import annotations

import html

from ..i18n import N_, tr, tr_name

# the variables' descriptions in the completion list (the Qt editor's TemplateTextEdit reads them from here too)
VARIABLE_DESCRIPTIONS = {
    "total_time": N_("Formatted total study time"),
    "reviews": N_("Number of reviews"),
    "ret_all": N_("Overall retention"),
    "ret_young": N_("Young-card retention"),
    "ret_mat": N_("Mature-card retention"),
    "streak": N_("Current streak"),
    "active_days": N_("Active days count"),
    "days_learned": N_("Share of days studied"),
    "longest_streak": N_("Longest streak"),
    "reviews_per_day": N_("Average reviews per day"),
    "time_per_day": N_("Average study time per day"),
    "reviews_per_active_day": N_("Average reviews per day studied"),
    "time_per_active_day": N_("Average study time per day studied"),
    "ret_true": N_("True retention (young and mature)"),
    "rev_young": N_("Young reviews"),
    "rev_mature": N_("Mature reviews"),
    "again": N_("Again count"),
    "best_day": N_("Most reviews in one day"),
    "cards_total": N_("Total cards"),
    "cards_new": N_("New cards"),
    "cards_learning": N_("Learning and relearning cards"),
    "cards_young": N_("Young cards"),
    "cards_mature": N_("Mature cards"),
    "cards_suspended": N_("Suspended cards"),
    "cards_buried": N_("Buried cards"),
    "cards_deleted": N_("Deleted cards"),
    "due_today": N_("Cards due today"),
    "backlog": N_("Overdue cards"),
    "avg_retrievability": N_("Average retrievability (FSRS)"),
    "avg_stability": N_("Average stability (FSRS)"),
    "lapses": N_("Failed review answers (young and mature)"),
}
UNITS = (("s", N_("Seconds")), ("min", N_("Minutes")), ("h", N_("Hours")), ("d", N_("Days")))
DECK_OVERRIDE_ORDER = ("current", "all", "deleted")


def _builder():
    from ..details.widgets.pinned.widget_factory.builders import text_label

    return text_label


def variables():
    return [[t, tr_name(VARIABLE_DESCRIPTIONS.get(t, t))] for t in _builder().AVAILABLE_VARS]


def spans(cfg=None):
    return [[t, d] for t, d in _builder().get_available_span_tokens(cfg)]


def decks():
    entries = _builder().get_available_deck_override_tokens()
    first = [e for e in entries if e[0] in DECK_OVERRIDE_ORDER]
    return [[t, d] for t, d in first + [e for e in entries if e[0] not in DECK_OVERRIDE_ORDER]]


def help_html(cfg=None):
    """The help under the editor (as the Qt editor's): a variable, its time span and deck, a duration's unit, "~",
    the Markdown. Its own HTML; the tab names in it escaped."""

    def code(text):
        return f"<code>{html.escape(text)}</code>"

    dot = " &middot; "

    def part(text):
        return f"<p>{text}</p>"

    vars_text = " ".join(code(f"{{{t}}}") for t in _builder().AVAILABLE_VARS)
    spans_text = dot.join(html.escape(t) for t, _d in _builder().get_available_span_tokens(cfg))
    return (
        part(tr("Type {open} to insert a variable, then use {colon} inside the placeholder for a time "
                "span override and {at} for a deck override.", open=code("{"), colon=code(":"), at=code("@")))
        + part(tr("<b>Variables</b>: {list}", list=vars_text))
        + part(tr("<b>Time spans</b>: {list}", list=spans_text) + "<br>"
               + tr("<i>Examples</i>: {list}", list=dot.join(
                   code(t) for t in ("{reviews:year}", "{reviews@current}", "{reviews:month@My Deck}"))))
        + part(tr("Use {bar} to pick the unit of a duration ({units}): {examples}",
                  bar=code("|"), units=", ".join(code(u) for u, _n in UNITS),
                  examples=dot.join(code(t) for t in ("{total_time|min}", "{avg_time|s}", "{time_per_day:month|min}"))))
        + part(tr("Add {tilde} before the closing brace so the text does not fade when that value "
                  "changes: {examples}. Right click a variable to switch it.",
                  tilde=code("~"), examples=dot.join(code(t) for t in ("{reviews~}", "{reviews:week|min~}"))))
        + part(tr("<b>Markdown</b> turns into formatting as you type it (Ctrl+Z gives the characters back): {examples}",
                  examples=dot.join(code(t) for t in
                                    ("# ", "## ", "- ", "1. ", "**bold**", "*italic*", "~~strike~~", "---"))))
    )


def editor_data(cfg=None):
    """{vars, spans, decks, units: [[token, description]], help: HTML}. cfg: the add-on's config (its tabs give the
    time spans; None: the add-on's own)."""
    from ..details.logic.logger import log_swallowed

    out = {"vars": [], "spans": [], "decks": [], "units": [[u, tr_name(n)] for u, n in UNITS], "help": ""}
    for key, fn in (("vars", variables), ("spans", lambda: spans(cfg)), ("decks", decks),
                    ("help", lambda: help_html(cfg))):
        try:
            out[key] = fn()
        except Exception:
            log_swallowed()
    return out


def keep_default(template, stored):
    """The template to save from the text editor: the default text, left as it was shown (translated), stays saved
    in English (so it follows a change of language)."""
    from ..const.config import TEXT_WIDGET_DEFAULT_TEMPLATE

    if stored == TEXT_WIDGET_DEFAULT_TEMPLATE and template == _builder().shown_template(stored):
        return TEXT_WIDGET_DEFAULT_TEMPLATE
    return template
