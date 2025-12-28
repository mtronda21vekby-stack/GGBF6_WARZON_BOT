# app/usecases/callbacks.py
from __future__ import annotations

from app.core.outgoing import Outgoing
from app.ui.keyboards import KB


async def handle_callback(brain, user_id: int, data: str) -> Outgoing:
    data = (data or "").strip()

    if data == "mem_clear":
        brain.clear_memory(user_id)
        return Outgoing(text="🧹 Память очищена.", keyboard=KB.main_menu())

    if data == "ai_mode":
        enabled = brain.toggle_ai(user_id)
        return Outgoing(text=f"🧠 ИИ-режим: {'ON' if enabled else 'OFF'}", keyboard=KB.main_menu())

    if data == "train":
        return Outgoing(text="🎯 Тренировка: напиши что именно хочешь прокачать (аим/мувмент/позиционка).", keyboard=KB.main_menu())

    if data == "profile":
        # если у тебя есть profiles внутри brain — он сам может вернуть профиль текстом
        # иначе просто заглушка:
        return Outgoing(text="📊 Профиль: в разработке (скоро добавим долгую память).", keyboard=KB.main_menu())

    if data == "settings":
        return Outgoing(text="⚙️ Настройки: в разработке.", keyboard=KB.main_menu())

    if data == "back":
        return Outgoing(text="⬅️ Ок, вернулись в меню.", keyboard=KB.main_menu())

    return Outgoing(text=f"⚙️ {data} (в разработке)", keyboard=KB.main_menu())
