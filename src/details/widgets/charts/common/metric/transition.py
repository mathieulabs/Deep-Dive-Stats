# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
def resolve_transition_align_right(transition_mode=None, transition_align_right=None):
    next_align_right = transition_mode == "timespan"
    if transition_align_right is not None:
        next_align_right = bool(transition_align_right)
    return next_align_right


def transition_update_is_redundant(widget, new_display, next_align_right, *, new_attr):
    return (
        widget._data_transition_active
        and bool(widget._transition_align_right) == bool(next_align_right)
        and list(new_display or []) == list(getattr(widget, new_attr, []) or [])
    )


def compute_global_transition_mode(old_total, new_total):
    if old_total <= 0.0 and new_total > 0.0:
        return "from_empty"
    if old_total > 0.0 and new_total <= 0.0:
        return "to_empty"
    return None


def apply_transition_state(
    widget,
    old_display,
    new_display,
    next_align_right,
    *,
    old_attr,
    new_attr,
    total_getter,
):
    setattr(widget, old_attr, old_display)
    setattr(widget, new_attr, new_display)
    widget._transition_align_right = bool(next_align_right)
    widget._data_transition_active = bool(old_display or new_display)
    old_total = float(total_getter(old_display))
    new_total = float(total_getter(new_display))
    widget._global_transition_mode = compute_global_transition_mode(old_total, new_total)
    return old_total, new_total


def _kept_zoom(widget, old_rows, new_rows):
    """((old_start, old_end), (new_start, new_end)) when the zoom is kept for this update."""
    st = getattr(widget, "_keep_zoom", None)
    if not st:
        return None
    from ....chart_utils.zoom_mixin import remap_zoom
    target = remap_zoom(st, new_rows)
    if not target:
        return None
    return (int(st[0]), int(st[1])), target


def zoom_slice_for_update(widget, old_data, new_data):
    """Rows the transition should animate: the zoom window when the zoom is kept, else everything."""
    kept = _kept_zoom(widget, old_data, new_data)
    if kept:
        (os_, oe), (ns, ne) = kept
        return old_data[os_:oe], new_data[ns:ne]
    # The zoom is dropped by this update, but the user sees the zoomed rows: start from those.
    if getattr(widget, "_is_zoomed", False) and len(old_data) == getattr(widget, "_full_length", -1):
        zs, ze = int(widget._zoom_start), int(widget._zoom_end)
        if 0 <= zs < ze <= len(old_data):
            return old_data[zs:ze], new_data
    return old_data, new_data


def commit_chart_data_update(widget, new_data):
    kept = _kept_zoom(widget, getattr(widget, "_full_data", None) or [], new_data)
    widget._full_data = new_data
    widget.data = new_data
    widget.init_zoom(len(new_data))
    widget._invalidate_data_caches()
    if kept:
        # Restore the zoom before the transition starts so the animation runs on the zoomed rows.
        widget.set_zoom_range(*kept[1])


def animate_transition_update(widget, transition_mode, *, old_attr, new_attr):
    old_display = getattr(widget, old_attr, []) or []
    new_display = getattr(widget, new_attr, []) or []
    if transition_mode == "timespan":
        return widget.animate_data_update(
            old_display,
            new_display,
            min_duration_ms=220,
            max_duration_ms=280,
            empty_transition_duration_ms=240,
        )
    return widget.animate_data_update(old_display, new_display)


def finalize_transition_state(widget, *, old_attr, new_attr):
    widget._data_transition_active = False
    setattr(widget, old_attr, [])
    setattr(widget, new_attr, [])
    widget._global_transition_mode = None
    widget._transition_align_right = False
