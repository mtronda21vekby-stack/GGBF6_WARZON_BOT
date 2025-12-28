from __future__ import annotations

from app.core.outgoing import Outgoing
from app.ui.keyboards import KB


QUICKMAP = {
    "📋 Меню": "menu:main",
    "⚙️ Настройки": "settings:menu",
    "🎮 Игра": "game:auto",
    "🎭 Стиль": "style:spicy",
    "💬 Ответ": "answer:normal",
    "🧟 Zombies": "zombies:menu",
    "🎯 Задание дня": "daily:task",
    "🎬 VOD": "vod:menu",
    "👤 Профиль": "profile:show",
    "📡 Статус": "status:show",
    "🆘 Помощь": "help:show",
    "🧹 Очистить память": "mem_clear",
    "🧨 Сброс": "reset:all",
}


async def handle_text_message(brain, profiles, handle_callback, user_id: int, text: str) -> Outgoing:
    text = (text or "").strip()
    if not text:
        return Outgoing("Напиши что-то 🙂", KB.main_inline(), ensure_quickbar=True)

    # если нажали нижнюю кнопку — превращаем в callback
    if text in QUICKMAP:
        return await handle_callback(brain, profiles, user_id, QUICKMAP[text])

    # обычный чат — отдаём в мозг
    reply = await brain.handle_text(user_id=user_id, text=text)
    return Outgoing(text=reply.text, inline_keyboard=KB.main_inline(), ensure_quickbar=True)
