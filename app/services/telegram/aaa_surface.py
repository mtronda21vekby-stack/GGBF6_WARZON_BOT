# -*- coding: utf-8 -*-
from __future__ import annotations

from copy import deepcopy
from functools import wraps
from typing import Mapping, Any

from app.i18n import normalize_locale
from app.ui.aaa_console import aaa_home_view, modules_view, war_room_view


def _aaa_home_actions(view: Any, profile: Mapping[str, Any]) -> Any:
    markup = deepcopy(view.reply_markup)
    rows = markup.get("inline_keyboard") if isinstance(markup, dict) else None
    if not isinstance(rows, list) or len(rows) < 2:
        return view
    locale = normalize_locale(profile.get("language_override") or profile.get("language") or "en")
    labels = {
        "ai": "🧠 AI СВОДКА" if locale == "ru" else "🧠 AI BRIEF",
        "operator": "ОПЕРАТОР" if locale == "ru" else "OPERATOR",
        "voice": "ГОЛОС" if locale == "ru" else "VOICE",
        "modules": "ВСЕ МОДУЛИ" if locale == "ru" else "ALL MODULES",
    }
    by_data = {
        str(button.get("callback_data") or ""): button
        for row in rows
        if isinstance(row, list)
        for button in row
        if isinstance(button, dict) and button.get("callback_data")
    }
    war = by_data.get("bco:warroom")
    operator = by_data.get("bco:profile")
    voice = by_data.get("bco:voice")
    modules = by_data.get("bco:modules")
    if not all((war, operator, voice, modules)):
        return view
    ai = {"text": labels["ai"], "callback_data": "bco:ai", "style": "primary"}
    operator = dict(operator); operator["text"] = labels["operator"]
    voice = dict(voice); voice["text"] = labels["voice"]
    modules = dict(modules); modules["text"] = labels["modules"]
    tail = [row for row in rows if not any(
        isinstance(button, dict) and str(button.get("callback_data") or "") in {"bco:warroom", "bco:profile", "bco:voice", "bco:modules"}
        for button in row
    )]
    markup["inline_keyboard"] = [[dict(war), ai], [operator, voice], [modules], *tail]
    return type(view)(text=view.text, reply_markup=markup)


def install() -> None:
    import app.services.telegram.command_console as cc
    from app.services.telegram.command_console import CommandConsoleController

    original_view = CommandConsoleController._view_for
    if getattr(original_view, "_bco_aaa_surface_v44", False):
        return

    @wraps(original_view)
    async def _view_for(self, action: str, chat_id: int, user_id: int):
        profile = self._profile(chat_id)
        if action == "home":
            view = aaa_home_view(profile, await self._operator_snapshot(chat_id))
            view = _aaa_home_actions(view, profile)
            if "COMMAND CONSOLE" not in view.text:
                view = type(view)(text=view.text.replace("// CROWN", "// COMMAND CONSOLE", 1), reply_markup=view.reply_markup)
            return view
        if action == "warroom":
            return war_room_view(profile, await self._operator_snapshot(chat_id))
        if action == "modules":
            return modules_view(profile)
        return await original_view(self, action, chat_id, user_id)

    original_callback = CommandConsoleController._handle_callback

    @wraps(original_callback)
    async def _handle_callback(self, callback: Mapping[str, Any]) -> bool:
        data = str(callback.get("data") or "").strip()
        if data not in {"bco:warroom", "bco:modules"}:
            return await original_callback(self, callback)

        callback_id = str(callback.get("id") or "").strip()
        message = callback.get("message") or {}
        message = message if isinstance(message, Mapping) else {}
        sender = cc._sender(callback)
        chat_id, user_id, _ = cc._private_identity(message, sender)
        if chat_id is None or user_id is None:
            if callback_id:
                try:
                    await self.tg.answer_callback_query(callback_id, "BLACK CROWN is available in a private chat.", show_alert=True)
                except Exception:
                    pass
            return True

        message_id = cc._int(message.get("message_id"))
        if message_id is None:
            return True
        if callback_id:
            try:
                await self.tg.answer_callback_query(callback_id)
            except Exception:
                pass
        action = data.removeprefix("bco:")
        await self._show(chat_id, await self._view_for(action, chat_id, user_id), message_id)
        return True

    _view_for._bco_aaa_surface_v44 = True
    _handle_callback._bco_aaa_surface_v44 = True
    CommandConsoleController._view_for = _view_for
    CommandConsoleController._handle_callback = _handle_callback
