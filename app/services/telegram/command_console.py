# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Mapping

from app.services.operator_intelligence import MissionConflict, OperatorIntelligenceService
from app.ui.command_console import (
    CALLBACK_PREFIX,
    ConsoleView,
    ai_view,
    brain_view,
    home_view,
    premium_unlink_confirm_view,
    premium_view,
    system_view,
    training_view,
    vod_view,
    world_view,
    zombies_view,
)
from app.ui.crown_voice_console import crown_voice_view, inject_home_voice_button
from app.ui.operator_console import operator_view
from app.ui.quickbar import _webapp_url

log = logging.getLogger("bco.command_console")

_OPEN_COMMANDS = {
    "/start", "/menu", "/deck", "/console", "/operator", "/mission",
    "Меню", "📋 Меню", "🧠 COMMAND DECK", "🛰 COMMAND CONSOLE",
}


def _message(raw: Mapping[str, Any]) -> Mapping[str, Any]:
    value = raw.get("message") or raw.get("edited_message") or {}
    return value if isinstance(value, Mapping) else {}


def _callback(raw: Mapping[str, Any]) -> Mapping[str, Any]:
    value = raw.get("callback_query") or {}
    return value if isinstance(value, Mapping) else {}


def _chat(message: Mapping[str, Any]) -> Mapping[str, Any]:
    value = message.get("chat") or {}
    return value if isinstance(value, Mapping) else {}


def _sender(container: Mapping[str, Any]) -> Mapping[str, Any]:
    value = container.get("from") or {}
    return value if isinstance(value, Mapping) else {}


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def _private_identity(message: Mapping[str, Any], sender: Mapping[str, Any]) -> tuple[int | None, int | None, str]:
    chat = _chat(message)
    chat_id = _int(chat.get("id"))
    user_id = _int(sender.get("id"))
    chat_type = str(chat.get("type") or "").strip().lower()
    if chat_type != "private" or chat_id is None or user_id is None or chat_id != user_id:
        return None, None, chat_type
    return chat_id, user_id, chat_type


@dataclass
class CommandConsoleController:
    tg: Any
    profiles: Any
    store: Any
    entitlements: Any
    settings: Any

    @property
    def enabled(self) -> bool:
        return bool(getattr(self.settings, "telegram_aaa_console_enabled", True))

    def _operator_service(self) -> OperatorIntelligenceService:
        return OperatorIntelligenceService(
            store=self.store,
            profiles=self.profiles,
            operator_enabled=bool(getattr(self.settings, "operator_intelligence_enabled", True)),
            missions_enabled=bool(getattr(self.settings, "adaptive_mission_control_enabled", True)),
        )

    async def configure_bot_surface(self) -> None:
        if not self.enabled:
            return
        commands = [
            {"command": "menu", "description": "Открыть COMMAND CONSOLE"},
            {"command": "operator", "description": "OPERATOR TWIN и текущая миссия"},
            {"command": "premium", "description": "Проверить Premium и связку аккаунта"},
            {"command": "voice", "description": "Настроить голосовой режим"},
            {"command": "vod", "description": "Открыть VOD-разбор"},
            {"command": "status", "description": "Проверить состояние системы"},
        ]
        try:
            await self.tg.set_my_commands(commands)
        except Exception as exc:
            log.warning("setMyCommands failed error=%s", type(exc).__name__)
        webapp_url = _webapp_url()
        if webapp_url:
            try:
                await self.tg.set_default_menu_button("COMMAND CENTER", webapp_url)
            except Exception as exc:
                log.warning("setChatMenuButton failed error=%s", type(exc).__name__)

    def _profile(self, chat_id: int) -> dict[str, Any]:
        try:
            return dict(self.profiles.get(chat_id) or {})
        except Exception:
            return {}

    async def _patch(self, chat_id: int, patch: Mapping[str, Any]) -> None:
        try:
            await asyncio.to_thread(self.profiles.patch, chat_id, dict(patch))
        except Exception as exc:
            log.warning("console profile patch failed error=%s", type(exc).__name__)

    async def _stats(self, chat_id: int) -> dict[str, Any]:
        fn = getattr(self.store, "stats", None)
        if not callable(fn):
            return {}
        try:
            result = await asyncio.to_thread(fn, chat_id)
            return dict(result or {}) if isinstance(result, Mapping) else {}
        except Exception:
            return {}

    async def _operator_snapshot(self, chat_id: int) -> dict[str, Any]:
        try:
            return await asyncio.to_thread(self._operator_service().snapshot, chat_id)
        except Exception as exc:
            log.warning("operator twin snapshot failed error=%s", type(exc).__name__)
            return {
                "operator": {"readiness": "UNAVAILABLE", "risk": "UNKNOWN", "confidence": "UNKNOWN", "session_momentum": "UNKNOWN"},
                "mission": {"title": "OPERATOR INTELLIGENCE UNAVAILABLE", "status": "candidate", "basis": "Transient runtime failure."},
                "session": {"phase": "PRE_SESSION"},
            }

    async def _premium_status(self, user_id: int) -> tuple[Any, str]:
        try:
            return await self.entitlements.get_status(user_id), ""
        except Exception as exc:
            log.warning("console Premium status failed error=%s", type(exc).__name__)
            return None, type(exc).__name__

    async def _show(self, chat_id: int, view: ConsoleView, message_id: int | None = None) -> None:
        if message_id is None:
            await self.tg.send_message(chat_id, view.text, view.reply_markup)
            return
        try:
            await self.tg.edit_message(chat_id, message_id, view.text, view.reply_markup)
        except Exception as exc:
            log.warning("console edit failed error=%s; sending replacement", type(exc).__name__)
            await self.tg.send_message(chat_id, view.text, view.reply_markup)

    async def _view_for(self, action: str, chat_id: int, user_id: int) -> ConsoleView:
        profile = self._profile(chat_id)
        if action == "home":
            return inject_home_voice_button(home_view(profile), profile)
        if action == "world":
            return world_view(profile)
        if action == "brain":
            return brain_view(profile)
        if action == "voice":
            return crown_voice_view(profile)
        if action in {"profile", "operator", "mission"}:
            return operator_view(await self._operator_snapshot(chat_id))
        if action == "system":
            return system_view(profile, await self._stats(chat_id))
        if action == "ai":
            return ai_view(profile)
        if action == "training":
            return training_view(profile)
        if action == "vod":
            return vod_view(profile)
        if action == "zombies":
            return zombies_view(profile)
        if action == "premium":
            status, error = await self._premium_status(user_id)
            return premium_view(status, error=error)
        return inject_home_voice_button(home_view(profile), profile)

    async def _open_from_message(self, message: Mapping[str, Any]) -> bool:
        sender = _sender(message)
        chat_id, user_id, _ = _private_identity(message, sender)
        if chat_id is None or user_id is None:
            return False
        try:
            await self.tg.remove_reply_keyboard(chat_id)
        except Exception as exc:
            log.warning("reply keyboard removal failed error=%s", type(exc).__name__)
        text = str(message.get("text") or "").strip()
        view = await self._view_for("operator" if text in {"/operator", "/mission"} else "home", chat_id, user_id)
        await self._show(chat_id, view)
        return True

    async def _handle_set(self, data: str, chat_id: int, user_id: int, message_id: int) -> bool:
        parts = data.split(":")
        if len(parts) != 4 or parts[0] != "bco" or parts[1] != "set":
            return False
        field, value = parts[2], parts[3]
        patch: dict[str, str]
        return_view: str
        if field == "game":
            mapped = {"wz": "Warzone", "bo7": "BO7", "bf6": "BF6"}.get(value)
            if not mapped:
                return False
            patch, return_view = {"game": mapped}, "world"
        elif field == "platform":
            mapped = {"pc": "PC", "ps": "PlayStation", "xbox": "Xbox"}.get(value)
            if not mapped:
                return False
            patch, return_view = {"platform": mapped}, "world"
        elif field == "input":
            mapped = {"controller": "Controller", "kbm": "KBM"}.get(value)
            if not mapped:
                return False
            patch, return_view = {"input": mapped}, "world"
        elif field == "brain":
            mapped = {"normal": "Normal", "pro": "Pro", "demon": "Demon"}.get(value)
            if not mapped:
                return False
            patch, return_view = {"difficulty": mapped}, "brain"
        elif field == "voice":
            mapped = {"teammate": "TEAMMATE", "coach": "COACH"}.get(value)
            if not mapped:
                return False
            patch, return_view = {"voice": mapped}, "voice"
        elif field == "voiceid":
            mapped = {
                "female": {"voice_identity": "female", "tts_voice": "marin"},
                "male": {"voice_identity": "male", "tts_voice": "cedar"},
            }.get(value)
            if not mapped:
                return False
            patch, return_view = mapped, "voice"
        elif field == "ttsmode":
            if value not in {"auto", "on_demand", "off"}:
                return False
            patch, return_view = {"tts_mode": value}, "voice"
        elif field == "focus":
            if value not in {"aim", "movement", "position"}:
                return False
            patch, return_view = {"training_focus": value}, "training"
        elif field == "zmap":
            mapped = {"ashes": "Ashes", "astra": "Astra"}.get(value)
            if not mapped:
                return False
            patch, return_view = {"zombies_map": mapped}, "zombies"
        else:
            return False
        await self._patch(chat_id, patch)
        await self._show(chat_id, await self._view_for(return_view, chat_id, user_id), message_id)
        return True

    async def _handle_premium(self, action: str, chat_id: int, user_id: int, username: str | None, message_id: int) -> None:
        if action == "unlink":
            await self._show(chat_id, premium_unlink_confirm_view(), message_id)
            return
        if action == "confirm":
            note = "Identity link удалён."
            try:
                removed = await self.entitlements.unlink(user_id)
                note = "Identity link удалён." if removed else "Активной связки не было."
            except Exception as exc:
                log.warning("console unlink failed error=%s", type(exc).__name__)
                status, error = await self._premium_status(user_id)
                await self._show(chat_id, premium_view(status, error=error or type(exc).__name__, note="Отвязка временно недоступна."), message_id)
                return
            status, error = await self._premium_status(user_id)
            await self._show(chat_id, premium_view(status, error=error, note=note), message_id)
            return
        if action != "link":
            await self._show(chat_id, await self._view_for("premium", chat_id, user_id), message_id)
            return
        if not bool(getattr(self.entitlements, "configured", False)):
            status, error = await self._premium_status(user_id)
            await self._show(chat_id, premium_view(status, error=error or "not_configured", note="Account Bridge не настроен."), message_id)
            return
        try:
            challenge = await self.entitlements.create_link_challenge(
                telegram_user_id=user_id,
                telegram_chat_id=chat_id,
                telegram_username=username,
            )
            status, error = await self._premium_status(user_id)
            minutes = max(1, int(challenge.ttl_seconds or 60) // 60)
            await self._show(chat_id, premium_view(
                status,
                error=error,
                link_url=str(challenge.url),
                link_ttl_minutes=minutes,
                note="Открой BlackCrown и подтверди текущий аккаунт.",
            ), message_id)
        except Exception as exc:
            log.warning("console link creation failed error=%s", type(exc).__name__)
            status, error = await self._premium_status(user_id)
            await self._show(chat_id, premium_view(status, error=error or type(exc).__name__, note="Не удалось создать одноразовую ссылку."), message_id)

    async def _handle_mission(self, data: str, chat_id: int, message_id: int) -> bool:
        parts = data.split(":")
        service = self._operator_service()
        try:
            if len(parts) == 4 and parts[:3] == ["bco", "m", "accept"]:
                snapshot = await asyncio.to_thread(service.accept, chat_id, parts[3])
                await self._show(chat_id, operator_view(snapshot, note="Mission accepted. LIVE OBJECTIVE is now active."), message_id)
                return True
            if len(parts) == 5 and parts[:3] == ["bco", "m", "complete"]:
                outcome, mission_id = parts[3], parts[4]
                snapshot = await asyncio.to_thread(service.complete, chat_id, mission_id, outcome=outcome, metrics={})
                await self._show(chat_id, operator_view(snapshot, note="Post-session result persisted. Operator Twin recalibrated."), message_id)
                return True
        except MissionConflict as exc:
            snapshot = await self._operator_snapshot(chat_id)
            await self._show(chat_id, operator_view(snapshot, note=f"Mission state changed: {exc}"), message_id)
            return True
        except Exception as exc:
            log.exception("mission console action failed error=%s", type(exc).__name__)
            snapshot = await self._operator_snapshot(chat_id)
            await self._show(chat_id, operator_view(snapshot, note="Mission action temporarily unavailable."), message_id)
            return True
        return False

    async def _handle_callback(self, callback: Mapping[str, Any]) -> bool:
        data = str(callback.get("data") or "").strip()
        if not data.startswith(CALLBACK_PREFIX):
            return False
        callback_id = str(callback.get("id") or "").strip()
        message = callback.get("message") or {}
        message = message if isinstance(message, Mapping) else {}
        sender = _sender(callback)
        chat_id, user_id, _ = _private_identity(message, sender)
        if chat_id is None or user_id is None:
            if callback_id:
                try:
                    await self.tg.answer_callback_query(callback_id, "COMMAND CONSOLE доступна в личном чате с ботом.", show_alert=True)
                except Exception:
                    pass
            return True
        message_id = _int(message.get("message_id"))
        if message_id is None:
            if callback_id:
                try:
                    await self.tg.answer_callback_query(callback_id, "Сообщение консоли недоступно.", show_alert=True)
                except Exception:
                    pass
            return True
        if callback_id:
            try:
                await self.tg.answer_callback_query(callback_id)
            except Exception:
                pass
        if data == "bco:close":
            try:
                await self.tg.delete_message(chat_id, message_id)
            except Exception:
                pass
            return True
        if data.startswith("bco:m:"):
            handled = await self._handle_mission(data, chat_id, message_id)
            if not handled:
                await self._show(chat_id, operator_view(await self._operator_snapshot(chat_id)), message_id)
            return True
        if data.startswith("bco:set:"):
            handled = await self._handle_set(data, chat_id, user_id, message_id)
            if not handled:
                await self._show(chat_id, inject_home_voice_button(home_view(self._profile(chat_id)), self._profile(chat_id)), message_id)
            return True
        if data.startswith("bco:p:"):
            action = data.removeprefix("bco:p:")
            username = str(sender.get("username") or "").strip() or None
            await self._handle_premium(action, chat_id, user_id, username, message_id)
            return True
        action = data.removeprefix(CALLBACK_PREFIX)
        allowed = {"home", "world", "brain", "voice", "profile", "operator", "mission", "system", "ai", "training", "vod", "zombies", "premium"}
        if action not in allowed:
            action = "home"
        await self._show(chat_id, await self._view_for(action, chat_id, user_id), message_id)
        return True

    async def maybe_handle(self, raw: Mapping[str, Any] | None) -> bool:
        if not self.enabled or not isinstance(raw, Mapping):
            return False
        callback = _callback(raw)
        if callback:
            return await self._handle_callback(callback)
        message = _message(raw)
        text = str(message.get("text") or "").strip()
        if text not in _OPEN_COMMANDS:
            return False
        return await self._open_from_message(message)
