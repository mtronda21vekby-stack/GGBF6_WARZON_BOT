# -*- coding: utf-8 -*-
from __future__ import annotations

from functools import wraps

from app.ui.aaa_console import aaa_home_view, modules_view, war_room_view


def install() -> None:
    from app.services.telegram.command_console import CommandConsoleController

    original = CommandConsoleController._view_for
    if getattr(original, "_bco_aaa_surface_v44", False):
        return

    @wraps(original)
    async def _view_for(self, action: str, chat_id: int, user_id: int):
        profile = self._profile(chat_id)
        if action == "home":
            return aaa_home_view(profile, await self._operator_snapshot(chat_id))
        if action == "warroom":
            return war_room_view(profile, await self._operator_snapshot(chat_id))
        if action == "modules":
            return modules_view(profile)
        return await original(self, action, chat_id, user_id)

    _view_for._bco_aaa_surface_v44 = True
    CommandConsoleController._view_for = _view_for
