# app/core/router.py  (ЗАМЕНИ ЦЕЛИКОМ)
from __future__ import annotations

from app.ui.quickbar import kb_main, kb_settings


class Router:
    def __init__(self, tg, brain, settings):
        self.tg = tg
        self.brain = brain
        self.settings = settings

    async def handle_update(self, upd):
        msg = getattr(upd, "message", None)
        if not msg:
            return

        chat_id = getattr(msg.chat, "id", None)
        text = (getattr(msg, "text", "") or "").strip()

        if not chat_id:
            return

        # Кнопки ReplyKeyboard (снизу)
        if text in ("/start", "Меню", "📋 Меню"):
            self.tg.send_message(chat_id, "✅ Бот жив. Напиши любое сообщение — я отвечу.", reply_markup=kb_main())
            return

        if text == "⚙️ Настройки":
            self.tg.send_message(chat_id, "⚙️ Настройки — выбери:", reply_markup=kb_settings())
            return

        if text == "⬅️ Назад":
            self.tg.send_message(chat_id, "⬅️ Назад в меню:", reply_markup=kb_main())
            return

        # Заглушка (пока без ИИ)
        self.tg.send_message(chat_id, f"Получил: {text}", reply_markup=kb_main())
