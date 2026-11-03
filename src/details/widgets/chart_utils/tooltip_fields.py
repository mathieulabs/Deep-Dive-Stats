# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Choice of the lines shown in chart tooltips.

Each tooltip line may carry an ``id``. A chart's ``tooltip_hidden`` attribute
lists the ids the user switched off; everything else stays visible, so the
default (empty list) is the full tooltip.
"""

from ....i18n import tr, N_, tr_name

# (id, label) shown as checkboxes in the settings dialogs.
HEATMAP_TOOLTIP_FIELDS = (
    ("reviews", N_("Reviews")),
    ("pending", N_("Today pending")),
    ("details", N_("Answer buttons / extra details")),
    ("time", N_("Time")),
    ("retention", N_("Retention")),
)

ACTIVITY_TOOLTIP_FIELDS = (
    ("total", N_("Running total")),
    ("mature", N_("Mature")),
    ("young", N_("Young")),
    ("relearn", N_("Relearning")),
    ("learn", N_("Learning")),
    ("cram", N_("Filtered")),
)

RETENTION_TOOLTIP_FIELDS = (
    ("all", N_("All")),
    ("young", N_("Young")),
    ("mature", N_("Mature")),
    ("true", N_("True retention")),
)

CHART_TOOLTIP_FIELDS = {
    "activity": ACTIVITY_TOOLTIP_FIELDS,
    "retention": RETENTION_TOOLTIP_FIELDS,
}


def filter_tooltip_lines(widget, lines):
    """Drop the lines whose id the chart hides. Headers are always kept."""
    hidden = getattr(widget, "tooltip_hidden", None)
    if not hidden or not lines:
        return lines
    hidden = set(hidden)
    return [ln for ln in lines if ln.get("header") or ln.get("id") not in hidden]


def build_tooltip_group(parent_layout, fields, hidden, title=None):
    """Add a group of checkboxes (checked = shown). Returns {id: QCheckBox}."""
    from aqt.qt import QCheckBox, QGroupBox, QVBoxLayout

    group = QGroupBox(title or tr("Tooltip"))
    box = QVBoxLayout(group)
    checks = {}
    hidden = set(hidden or ())
    for fid, label in fields:
        cb = QCheckBox(tr_name(label))
        cb.setChecked(fid not in hidden)
        box.addWidget(cb)
        checks[fid] = cb
    parent_layout.addWidget(group)
    return checks


def hidden_from_checks(checks):
    return [fid for fid, cb in checks.items() if not cb.isChecked()]


def set_checks(checks, hidden):
    hidden = set(hidden or ())
    for fid, cb in checks.items():
        cb.setChecked(fid not in hidden)
