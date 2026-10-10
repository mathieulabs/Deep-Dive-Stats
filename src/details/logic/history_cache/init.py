# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .ops.init import init_async as init_async_impl, on_profile_switch as on_profile_switch_impl


class InitMixin:
    def _on_collection_loaded(self, *args, **kwargs):
        # At startup the cache is not initialized yet and profile_did_open does the work.
        if not self.is_initialized:
            return
        return on_profile_switch_impl(self, GlobalHistoryCache, *args, **kwargs)

    def _on_profile_switch(self, *args, **kwargs):
        return on_profile_switch_impl(self, GlobalHistoryCache, *args, **kwargs)

    @staticmethod
    def init_async(callback=None):
        return init_async_impl(GlobalHistoryCache, callback=callback)

