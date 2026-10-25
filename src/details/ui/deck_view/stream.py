# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from aqt import mw

from .. import Config
from ...logic.refresh import queue_ui_callback
from .queue import build_initial_fetch_queue
from ...logic.logger import log_error


def start_deck_streaming(
    dialog,
    gen,
    deck_tree,
    tab_widget,
    tabs_config,
    show_trends,
    deleted_tab_did="__deleted_cards__",
    populate_deck_tab_fn=None,
):
    """Start asynchronous per-deck streaming fetch/populate."""
    dialog._deck_fetch_queue = build_initial_fetch_queue(
        tab_widget, deck_tree, deleted_tab_did=deleted_tab_did
    )

    def _deck_view_ui_alive():
        try:
            tab_w = getattr(dialog, "tab_widget", None)
            if tab_w is None:
                return False
            tab_w.currentIndex()
            return True
        except RuntimeError:
            return False
        except Exception:
            return False

    def process_deck_queue():
        if not _deck_view_ui_alive():
            return
        if dialog.load_generation != gen:
            return

        if not dialog._deck_fetch_queue:
            if getattr(dialog, "_deck_view_cache", None):
                dialog._deck_view_cache["complete"] = True
                dialog._deck_view_cache["deck_view_data"] = dict(dialog.deck_view_data)
                dialog._deck_view_cache["tab_stats"] = dict(dialog.tab_stats)
            return

        current_idx = dialog.tab_widget.currentIndex()
        current_tab = dialog.tab_widget.widget(current_idx)
        if current_tab:
            current_did = current_tab.property("deck_id")
            if current_did in dialog._deck_fetch_queue:
                dialog._deck_fetch_queue.remove(current_did)
                dialog._deck_fetch_queue.insert(0, current_did)

        target_did = dialog._deck_fetch_queue.pop(0)

        def fetch_task():
            from ...logic.data import fetch_deck_stats

            is_col = target_did == "collection"
            is_deleted = target_did == deleted_tab_did
            search_did = None if (is_col or is_deleted) else target_did

            result = fetch_deck_stats(
                search_did,
                tabs_config,
                excluded_dids=dialog.addon_config.config.get(Config.EXCLUDED_DECKS, []),
                show_trends=show_trends,
                week_start=dialog.addon_config.config.get(Config.WEEK_START, 0),
                spark_precision=dialog.addon_config.config.get(Config.SPARKLINE_PRECISION, False),
                is_collection=is_col,
            )
            return result

        def on_fetch_done(future):
            if not _deck_view_ui_alive():
                return
            if dialog.load_generation != gen:
                return
            try:
                stats_list = future.result()
                dialog.deck_view_data[target_did] = stats_list
                if getattr(dialog, "_deck_view_cache", None):
                    dialog._deck_view_cache["deck_view_data"] = dict(dialog.deck_view_data)

                should_resize = False
                for i in range(dialog.tab_widget.count()):
                    w = dialog.tab_widget.widget(i)
                    if w and w.property("deck_id") == target_did:
                        should_resize = i == dialog.tab_widget.currentIndex()
                        if should_resize and populate_deck_tab_fn is not None:
                            populate_deck_tab_fn(dialog, i, do_resize=True)
                        break

                if getattr(dialog, "_deck_view_cache", None):
                    dialog._deck_view_cache["tab_stats"] = dict(dialog.tab_stats)

                next_delay_ms = 140 if should_resize else 5
                queue_ui_callback(
                    process_deck_queue,
                    delay_ms=next_delay_ms,
                    owner=dialog,
                    reason="deck_view.stream_next_success",
                )
            except Exception as e:
                import traceback

                err_msg = (
                    f"[ERROR] Deck fetch failed for {target_did}: {str(e)}\n"
                    f"{traceback.format_exc()}"
                )
                log_error(err_msg)

                queue_ui_callback(
                    process_deck_queue,
                    delay_ms=5,
                    owner=dialog,
                    reason="deck_view.stream_next_error",
                )

        mw.taskman.run_in_background(fetch_task, on_fetch_done)

    process_deck_queue()

