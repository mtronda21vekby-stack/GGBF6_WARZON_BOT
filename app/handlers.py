# -*- coding: utf-8 -*-

from app.ui import (
    show_main_menu,
    show_game_menu,
    show_style_menu,
    show_settings_menu,
)
from app.state import ensure_profile
from app.log import log


class BotHandlers:
    def __init__(self, api, ai_engine):
        self.api = api
        self.ai = ai_engine

    def handle_text(self, chat_id: int, text: str):
        text = text.strip()

        # ===== МЕНЮ =====
        if text in ("Меню", "📋 Меню"):
            return self.api.send_message(
                chat_id,
                "📋 Главное меню",
                reply_markup=show_main_menu()
            )

        # ===== ИГРА =====
        if text in ("Игра", "🎮 Игра"):
            return self.api.send_message(
                chat_id,
                "🎮 Выбери игру",
                reply_markup=show_game_menu()
            )

        # ===== СТИЛЬ =====
        if text in ("Стиль", "🎭 Стиль"):
            return self.api.send_message(
                chat_id,
                "🎭 Выбери стиль игры",
                reply_markup=show_style_menu()
            )

        # ===== НАСТРОЙКИ =====
        if text in ("Настройки", "⚙️ Настройки"):
            return self.api.send_message(
                chat_id,
                "⚙️ Настройки бота",
                reply_markup=show_settings_menu()
            )

        # ===== ZOMBIES =====
        if text in ("Zombies", "🧟 Zombies"):
            return self.api.send_message(
                chat_id,
                "🧟 Zombies режим активирован"
            )

        # ===== ПРОФИЛЬ =====
        if text == "Профиль":
            p = ensure_profile(chat_id)
            return self.api.send_message(
                chat_id,
                f"👤 Профиль:\n"
                f"Игра: {p.get('game','auto')}\n"
                f"Стиль: {p.get('persona','spicy')}\n"
                f"Ответы: {p.get('verbosity','normal')}"
            )

        # ===== ОЧИСТКА ПАМЯТИ =====
        if text == "Очистить память":
            p = ensure_profile(chat_id)
            p["memory"] = []
            return self.api.send_message(chat_id, "🧹 Память очищена")

        # ===== СБРОС =====
        if text == "Сброс":
            ensure_profile(chat_id, reset=True)
            return self.api.send_message(chat_id, "🔄 Всё сброшено")

        # ===== FALLBACK → BRAIN v3 =====
        log.info("Brain v3 handling message")
        return self.ai.reply(chat_id, text)
