# app/core/router.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any

from app.core import router_base as _base
from app.core.router_base import *  # noqa: F401,F403 - compatibility export
from app.i18n import resolve_locale, telegram_message, telegram_user, tr
from app.services.analytics.admin_usage import AdminUsageAnalytics
from app.services.telegram.admin_console import AdminConsoleController
from app.services.telegram.live_response import TelegramLiveResponse

log = logging.getLogger("router.live")


def __getattr__(name: str) -> Any:
    return getattr(_base, name)


def _accepts_partial(fn: Any) -> bool:
    try: signature = inspect.signature(fn)
    except Exception: return True
    if "on_partial" in signature.parameters: return True
    return any(p.kind == inspect.Parameter.VAR_KEYWORD for p in signature.parameters.values())


def _clean_ecosystem_profile_patch(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate v56 cross-surface profile fields before persistent storage."""
    source = payload.get("profile") if isinstance(payload.get("profile"), dict) else payload
    if not isinstance(source, dict):
        return {}
    out: dict[str, Any] = {}

    name = str(source.get("profile_name") or "").strip()
    if name:
        out["profile_name"] = name[:32]

    identity = str(source.get("voice_identity") or "").strip().lower()
    if identity in {"female", "male"}:
        out["voice_identity"] = identity
        # Voice identity owns the default synthetic voice. Do not accept an
        # arbitrary model voice from the Mini App as server authority.
        out["tts_voice"] = "marin" if identity == "female" else "cedar"

    tts_mode = str(source.get("tts_mode") or "").strip().lower()
    if tts_mode in {"auto", "on_demand", "off"}:
        out["tts_mode"] = tts_mode

    focus = str(source.get("training_focus") or source.get("focus") or "").strip().lower()
    if focus in {"aim", "movement", "position", "positioning"}:
        out["training_focus"] = "position" if focus == "positioning" else focus

    return out


class Router(_base.Router):
    """Production Router with live intelligence + ecosystem profile boundary."""

    def _locale_profile(self, chat_id: int, update: dict, text: str) -> tuple[dict, str, int | None]:
        profile = self._get_profile(chat_id)
        locale = resolve_locale(raw=update, profile=profile, text=text)
        user = telegram_user(update)
        try: user_id = int(user.get("id"))
        except Exception: user_id = None
        if str(profile.get("language_override") or "").strip() == "":
            try: self.profiles.patch(chat_id, {"language": locale})
            except Exception: pass
            profile["language"] = locale
        else:
            locale = resolve_locale(raw=update, profile=profile, text=None)
        return profile, locale, user_id

    def _record_activity(self, *, user_id: int | None, chat_id: int, locale: str, update: dict, text: str) -> None:
        if user_id is None or user_id <= 0: return
        msg = telegram_message(update)
        voice = bool(msg.get("voice") or msg.get("audio") or msg.get("video_note") or str(msg.get("_bco_input_mode") or "").startswith("voice"))
        # Callback data is navigation telemetry, not a user message. The old
        # bool(text) contract counted every inline-button tap as a message.
        message_text = str(msg.get("text") or msg.get("caption") or "").strip()
        try:
            AdminUsageAnalytics(self.store).record(
                user_id=user_id,
                chat_id=chat_id,
                language=locale,
                surface="telegram_voice" if voice else "telegram",
                is_message=bool(message_text),
                is_voice=voice,
            )
        except Exception as exc:
            log.warning("usage analytics record failed error=%s", type(exc).__name__)

    async def handle_update(self, update: Any) -> None:
        raw = _base._to_update_dict(update)
        msg = raw.get("message") or raw.get("edited_message") or {}
        cbq = raw.get("callback_query") or {}
        chat_id = _base._safe_get(msg, ["chat", "id"]) if msg else _base._safe_get(cbq, ["message", "chat", "id"])
        text = str((msg.get("text") if isinstance(msg, dict) else "") or (cbq.get("data") if isinstance(cbq, dict) else "") or "").strip()
        if chat_id:
            profile, locale, user_id = self._locale_profile(int(chat_id), raw, text)
            self._record_activity(user_id=user_id, chat_id=int(chat_id), locale=locale, update=raw, text=text)

            admin = AdminConsoleController(tg=self.tg, store=self.store, profiles=self.profiles, settings=self.settings)
            if await admin.maybe_handle(raw):
                return

            if text in {"/lang", "/language", "bco:language"}:
                await self._send_main(int(chat_id), tr(locale, "Язык BLACK CROWN OPS: Русский.\nПереключить: /lang_en\nАвтоопределение: /lang_auto", "BLACK CROWN OPS language: English.\nSwitch: /lang_ru\nAuto-detect: /lang_auto"))
                return
            if text in {"/lang_en", "/lang_ru", "/lang_auto"}:
                patch = {"language_override": "", "language": locale} if text == "/lang_auto" else {"language_override": "en" if text == "/lang_en" else "ru", "language": "en" if text == "/lang_en" else "ru"}
                try: self.profiles.patch(int(chat_id), patch)
                except Exception: pass
                chosen = patch.get("language") or locale
                await self._send_main(int(chat_id), tr(chosen, "✅ Вся экосистема переключена на русский.", "✅ The ecosystem is now switched to English."))
                return

        await super().handle_update(raw)

    async def _on_webapp_data(self, chat_id: int, data: str) -> None:
        """Persist v56 ecosystem fields, then delegate all established routing."""
        payload = _base._safe_json_loads(str(data or "").strip())
        if isinstance(payload, dict):
            ptype = str(payload.get("type") or "").strip().lower()
            patch: dict[str, Any] = {}
            if ptype in {"set_profile", "profile", "settings"}:
                patch.update(_clean_ecosystem_profile_patch(payload))
            if ptype == "training_plan":
                focus = str(payload.get("focus") or "").strip().lower()
                if focus in {"aim", "movement", "position", "positioning"}:
                    patch["training_focus"] = "position" if focus == "positioning" else focus
            if patch and self.profiles is not None:
                try:
                    self.profiles.patch(int(chat_id), patch)
                    log.info("ecosystem profile sync chat=%s fields=%s", chat_id, sorted(patch))
                except Exception as exc:
                    log.warning("ecosystem profile sync failed error=%s", type(exc).__name__)
        await super()._on_webapp_data(chat_id, data)

    async def _chat_to_brain(self, chat_id: int, text: str) -> None:
        text = (text or "").strip()
        profile = self._get_profile(chat_id)
        locale = resolve_locale(profile=profile, text=text)
        if str(profile.get("language_override") or "").strip() == "":
            try: self.profiles.patch(chat_id, {"language": locale})
            except Exception: pass
            profile["language"] = locale
        if not text:
            await self._send_main(chat_id, _base._wrap_premium(tr(locale, "🤝 Напиши ситуацию текстом. Пустой запрос анализировать нечего.", "🤝 Describe the situation in text. There is nothing to analyze in an empty request."), profile=profile)); return
        if len(text) > 6000: text = _base._truncate(text, 6000)
        if self.store and hasattr(self.store, "add"):
            try: self.store.add(chat_id, "user", text)
            except Exception: pass
        history=[]
        if self.store and hasattr(self.store,"get"):
            try: history=list(self.store.get(chat_id) or [])
            except Exception: history=[]
        live_enabled=bool(getattr(self.settings,"telegram_live_drafts_enabled",True) if self.settings is not None else True)
        live=TelegramLiveResponse(tg=self.tg,chat_id=chat_id)
        if live_enabled:
            try: await live.start()
            except Exception: live_enabled=False
        try:
            action=getattr(self.tg,"send_chat_action",None)
            if callable(action):
                try: await action(chat_id,"typing")
                except Exception: pass
            reply=None
            if self.brain and hasattr(self.brain,"reply"):
                try:
                    fn=self.brain.reply; kwargs={"text":text,"profile":profile,"history":history}
                    if live_enabled and _accepts_partial(fn): kwargs["on_partial"]=live.publish_from_thread
                    reply=await fn(**kwargs) if inspect.iscoroutinefunction(fn) else await asyncio.to_thread(fn,**kwargs)
                except Exception as exc:
                    log.exception("live intelligence generation failed error=%s",type(exc).__name__)
                    reply=tr(locale,"🧠 Канал анализа временно не завершил ответ. Профиль и память сохранены. Повтори запрос через несколько секунд.","🧠 The analysis channel could not complete the response. Your profile and memory are safe. Try again in a few seconds.")
            if not reply:
                voice=_base._norm_voice(profile.get("voice","TEAMMATE"))
                if voice=="COACH": reply=tr(locale,"📚 Нужны три факта: игра и режим, input и где ломается решение.","📚 I need three facts: game/mode, input, and where the decision breaks down.")
                else: reply=tr(locale,"🤝 Дай одной строкой: игра | input | где умер | чего хотел добиться.","🤝 One line: game | input | where you died | what you were trying to achieve.")
            final_reply=str(reply)
            if live_enabled:
                try: await live.finish(final_reply)
                except Exception: pass
            if self.store and hasattr(self.store,"add"):
                try: self.store.add(chat_id,"assistant",final_reply)
                except Exception: pass
            await self._send_main(chat_id,_base._wrap_premium(final_reply,profile=profile))
        finally:
            if live_enabled:
                try: await live.finish("")
                except Exception: pass
