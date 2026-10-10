# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
def set_chart_opacity_impl(widget, pct):
    widget.chart_opacity_pct = max(0, min(100, int(pct)))
    widget.update()


def binning_active_getter(widget):
    if widget.binning_override is not None:
        return widget.binning_override
    return widget.adaptive_binning


def set_flag_and_update(widget, attr, value):
    setattr(widget, str(attr), value)
    widget.update()


def set_flags_and_update(widget, value, *attrs):
    for attr in attrs:
        if attr:
            setattr(widget, str(attr), value)
    widget.update()
