# -*- coding: utf-8 -*-
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


# MIGRATION-ONLY: current main still composes Telegram UI through additive
# import-time layers. Keep this compatibility boundary narrow and explicit so
# Phase 5 can delete it when CommandConsoleController owns one Action Router and
# one Locale Renderer directly.


def install_locale_compatibility() -> None:
    """Register current source labels before the legacy locale wrapper installs."""

    from app.services.telegram import console_i18n as i18n

    i18n._RU_BUTTONS.update(
        {
            "🧠 CROWN ИИ": "🧠 AI СВОДКА",
            "🎮 ИГРОВОЙ МИР": "🎮 ИГРА",
            "🎬 VOD ЛАБ": "🎬 VOD РАЗБОР",
            "💎 PREMIUM": "💎 ПРЕМИУМ",
            "⚙️ СИСТЕМА": "⚙️ СИСТЕМА",
            "🛰 КОМАНДНЫЙ ЦЕНТР": "🛰 ЦЕНТР УПРАВЛЕНИЯ",
        }
    )
    i18n._EN_BUTTONS.update(
        {
            "🧠 CROWN ИИ": "🧠 AI BRIEF",
            "🎮 ИГРОВОЙ МИР": "🎮 WORLD",
            "🎬 VOD ЛАБ": "🎬 VOD LAB",
            "🧟 ЗОМБИ": "🧟 ZOMBIES",
            "📌 ОПЕРАТОР": "📌 OPERATOR",
            "💎 ПРЕМИУМ": "💎 PREMIUM",
            "⚙️ СИСТЕМА": "⚙️ SYSTEM",
            "🛰 КОМАНДНЫЙ ЦЕНТР": "🛰 COMMAND CENTER",
            "↻ ОБНОВИТЬ": "↻ REFRESH",
            "✕ ЗАКРЫТЬ": "✕ CLOSE",
        }
    )
    i18n._EN_TEXT.update(
        {
            "КОМАНДНАЯ КОНСОЛЬ": "COMMAND CONSOLE",
            "ОПЕРАТОР //": "OPERATOR //",
            "СВЯЗЬ // В СЕТИ": "LINK // ONLINE",
            "ТЕКУЩИЙ КОНТЕКСТ:": "CURRENT CONTEXT:",
            "• МИР —": "• WORLD —",
            "• ПЛАТФОРМА —": "• PLATFORM —",
            "• ЯДРО —": "• CORE —",
            "• РОЛЬ —": "• ROLE —",
            "Выбери модуль. Бот и Mini App используют один профиль оператора.": (
                "Choose a module. Bot and Mini App use one operator profile."
            ),
        }
    )


def install_controller_compatibility() -> None:
    """Restore the established webhook entrypoint and stable callback aliases."""

    import app.services.telegram.command_console as module

    controller = module.CommandConsoleController
    existing = getattr(controller, "maybe_handle", None)
    if callable(existing) and getattr(existing, "_bco_runtime_compat_v1", False):
        return

    async def maybe_handle(self: Any, raw: Mapping[str, Any] | Any) -> bool:
        if not self.enabled or not isinstance(raw, Mapping):
            return False

        callback = module._callback(raw)
        adapted: Mapping[str, Any] = raw
        if callback:
            data = str(callback.get("data") or "").strip()
            if data.startswith(module.CALLBACK_PREFIX):
                message = callback.get("message") or {}
                message = message if isinstance(message, Mapping) else {}
                sender = module._sender(callback)
                chat_id, user_id, _ = module._private_identity(message, sender)
                if chat_id is None or user_id is None:
                    callback_id = str(callback.get("id") or "").strip()
                    if callback_id:
                        try:
                            await self.tg.answer_callback_query(
                                callback_id,
                                "COMMAND CONSOLE доступна в личном чате с ботом.",
                                show_alert=True,
                            )
                        except Exception:
                            pass
                    return True

                # Preserve the short callback namespace used by already-sent
                # inline messages while the current controller uses the explicit
                # ``bco:premium:*`` route internally.
                if data.startswith("bco:p:"):
                    adapted_raw = deepcopy(dict(raw))
                    adapted_callback = dict(adapted_raw.get("callback_query") or {})
                    adapted_callback["data"] = "bco:premium:" + data.removeprefix("bco:p:")
                    adapted_raw["callback_query"] = adapted_callback
                    adapted = adapted_raw

        return await self.handle_update(adapted)

    maybe_handle._bco_runtime_compat_v1 = True
    controller.maybe_handle = maybe_handle
