# app/core/router.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any

from app.core import router_base as _base
from app.core.router_base import *  # noqa: F401,F403 - compatibility export
from app.services.telegram.live_response import TelegramLiveResponse


log = logging.getLogger("router.live")


def __getattr__(name: str) -> Any:
    """Preserve access to legacy helper symbols during incremental migration."""
    return getattr(_base, name)


def _accepts_partial(fn: Any) -> bool:
    try:
        signature = inspect.signature(fn)
    except Exception:
        return True
    if "on_partial" in signature.parameters:
        return True
    return any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )


class Router(_base.Router):
    """Production Router with live Telegram intelligence presentation.

    All deterministic menus and world presets remain in router_base. Only the
    expensive free-form AI boundary is overridden, which keeps the migration
    controlled and makes the live draft layer independently reversible.
    """

    async def _chat_to_brain(self, chat_id: int, text: str) -> None:
        text = (text or "").strip()
        if not text:
            profile = self._get_profile(chat_id)
            await self._send_main(
                chat_id,
                _base._wrap_premium(
                    "🤝 Напиши ситуацию текстом. Пустой запрос анализировать нечего.",
                    profile=profile,
                ),
            )
            return

        if len(text) > 6000:
            text = _base._truncate(text, 6000)

        if self.store and hasattr(self.store, "add"):
            try:
                self.store.add(chat_id, "user", text)
            except Exception:
                pass

        profile = self._get_profile(chat_id)
        history: list[dict] = []
        if self.store and hasattr(self.store, "get"):
            try:
                history = list(self.store.get(chat_id) or [])
            except Exception:
                history = []

        live_enabled = bool(
            getattr(self.settings, "telegram_live_drafts_enabled", True)
            if self.settings is not None
            else True
        )
        live = TelegramLiveResponse(tg=self.tg, chat_id=chat_id)
        if live_enabled:
            try:
                await live.start()
            except Exception:
                live_enabled = False

        try:
            action = getattr(self.tg, "send_chat_action", None)
            if callable(action):
                try:
                    await action(chat_id, "typing")
                except Exception:
                    pass

            reply: Any = None
            if self.brain and hasattr(self.brain, "reply"):
                try:
                    fn = self.brain.reply
                    kwargs: dict[str, Any] = {
                        "text": text,
                        "profile": profile,
                        "history": history,
                    }
                    if live_enabled and _accepts_partial(fn):
                        kwargs["on_partial"] = live.publish_from_thread

                    if inspect.iscoroutinefunction(fn):
                        reply = await fn(**kwargs)
                    else:
                        # The existing OpenAI client is synchronous. Running it
                        # in a worker thread keeps FastAPI responsive while the
                        # event loop renders native Telegram draft updates.
                        reply = await asyncio.to_thread(fn, **kwargs)
                except Exception as exc:
                    log.exception("live intelligence generation failed error=%s", type(exc).__name__)
                    reply = (
                        "🧠 Канал анализа временно не завершил ответ.\n"
                        f"Класс ошибки: {type(exc).__name__}.\n\n"
                        "Профиль и память сохранены. Повтори запрос через несколько секунд."
                    )

            if not reply:
                voice = _base._norm_voice(profile.get("voice", "TEAMMATE"))
                if voice == "COACH":
                    reply = (
                        "📚 Нужны три факта для точного разбора:\n"
                        "• игра и режим\n"
                        "• input\n"
                        "• где именно ломается решение\n\n"
                        "После этого дам причину, правило, корректировку и метрику."
                    )
                else:
                    reply = (
                        "🤝 Дай одной строкой: игра | input | где умер | чего хотел добиться.\n\n"
                        "Верну главный косяк, три правила на следующий файт и короткий drill."
                    )

            final_reply = str(reply)
            if live_enabled:
                try:
                    await live.finish(final_reply)
                except Exception:
                    pass

            if self.store and hasattr(self.store, "add"):
                try:
                    self.store.add(chat_id, "assistant", final_reply)
                except Exception:
                    pass

            await self._send_main(
                chat_id,
                _base._wrap_premium(final_reply, profile=profile),
            )
        finally:
            if live_enabled:
                try:
                    await live.finish("")
                except Exception:
                    pass
