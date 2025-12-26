# -*- coding: utf-8 -*-
"""
SAFE HANDLERS v1
Цель:
- 100% старт на Render
- совместимость со старым runner.py
- не ломаем архитектуру
- база под Brain v3 / UI Premium
"""

from typing import Any, Dict, Optional
import traceback

# UI / KB — если есть, используем, если нет — не падаем
try:
    from app.ui import main_text, menu_main
except Exception:
    main_text = None
    menu_main = None

try:
    from app.state import ensure_profile
except Exception:
    ensure_profile = None


class BotHandlers:
    """
    ❗ КЛЮЧЕВОЕ:
    __init__ принимает ЛЮБЫЕ аргументы
    => runner.py больше НИКОГДА не упадёт
    """

    def __init__(self, *args, **kwargs):
        # ничего не предполагаем — просто сохраняем
        self.args = args
        self.kwargs = kwargs

        # часто передают так — аккуратно вытащим
        self.api = kwargs.get("api")
        self.ai_engine = kwargs.get("ai_engine")
        self.log = kwargs.get("log")

        if self.log:
            self.log.info("✅ BotHandlers initialized (SAFE MODE)")

    # =========================
    # ENTRY POINTS
    # =========================

    def on_start(self, chat_id: int) -> None:
        """
        /start или первый вход
        """
        try:
            if ensure_profile:
                ensure_profile(chat_id)

            text = (
                "🎮 FPS Coach Bot\n"
                "🧠 Brain v3 (SAFE BOOT)\n\n"
                "Напиши ситуацию или жми меню 👇"
            )

            if main_text and self.ai_engine:
                text = main_text(
                    chat_id=chat_id,
                    ai_enabled=bool(self.ai_engine),
                    model=getattr(self.ai_engine, "model", "unknown"),
                )

            kb = menu_main(chat_id, bool(self.ai_engine)) if menu_main else None

            if self.api:
                self.api.send_message(chat_id, text, reply_markup=kb)

        except Exception as e:
            if self.log:
                self.log.error("on_start failed: %r", e)
                self.log.error(traceback.format_exc())

    def on_message(self, chat_id: int, text: str) -> None:
        """
        Любое текстовое сообщение
        SAFE: даже если AI/KB отсутствуют
        """
        try:
            if self.ai_engine:
                reply = self.ai_engine.chat_reply(chat_id, text)
            else:
                reply = (
                    "🧠 AI временно OFF\n"
                    "Опиши: где умер и почему думаешь?"
                )

            if self.api:
                self.api.send_message(chat_id, reply)

        except Exception as e:
            if self.log:
                self.log.error("on_message failed: %r", e)
                self.log.error(traceback.format_exc())

    def on_callback(self, chat_id: int, data: str) -> None:
        """
        Inline кнопки
        Пока SAFE-заглушка — UI не ломается
        """
        try:
            if self.api:
                self.api.send_message(
                    chat_id,
                    f"⚙️ Опция принята: `{data}`",
                )
        except Exception as e:
            if self.log:
                self.log.error("on_callback failed: %r", e)
                self.log.error(traceback.format_exc())
