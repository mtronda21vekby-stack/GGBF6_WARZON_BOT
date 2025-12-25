# app/ui.py
# -*- coding: utf-8 -*-

def _badge(ok: bool) -> str:
    return "✅" if ok else "🚫"

def main_menu_markup(p: dict, ai_on: bool):
    """
    Главное меню:
    - оставляем верхние настройки
    - оставляем Zombies
    - всё остальное прячем под кнопку 📦 Ещё
    """
    game = (p.get("game", "auto") or "auto").upper()
    persona = p.get("persona", "spicy")
    talk = p.get("verbosity", "normal")
    mode = (p.get("mode", "chat") or "chat").upper()

    mem_on = (p.get("memory", "on") == "on")
    lightning_on = (p.get("lightning", "off") == "on")

    return {
        "inline_keyboard": [
            [
                {"text": f"🎮 Игра: {game}", "callback_data": "nav:game"},
                {"text": f"🎭 Стиль: {persona}", "callback_data": "nav:persona"},
            ],
            [
                {"text": f"💬 Ответ: {talk}", "callback_data": "nav:talk"},
                {"text": f"{_badge(mem_on)} Память", "callback_data": "toggle:memory"},
            ],
            [
                {"text": f"🔁 Режим: {mode}", "callback_data": "toggle:mode"},
                {"text": f"🤖 ИИ: {'ON' if ai_on else 'OFF'}", "callback_data": "action:ai_status"},
            ],
            [
                {"text": f"⚡ Молния: {'ВКЛ' if lightning_on else 'ВЫКЛ'}", "callback_data": "toggle:lightning"},
                {"text": "🧟 Zombies", "callback_data": "zmb:home"},  # ВАЖНО: zmb:home
            ],
            [
                {"text": "📦 Ещё", "callback_data": "ui:more"},
            ],
        ]
    }

def more_menu_markup():
    return {
        "inline_keyboard": [
            [
                {"text": "💪 Тренировка", "callback_data": "nav:training"},
                {"text": "📊 Профиль", "callback_data": "action:profile"},
                {"text": "⚙️ Настройки", "callback_data": "nav:settings"},
            ],
            [
                {"text": "🎯 Задание дня", "callback_data": "action:daily"},
                {"text": "📼 VOD-разбор", "callback_data": "action:vod"},
            ],
            [
                {"text": "🧽 Очистить память", "callback_data": "action:clear_memory"},
                {"text": "🧨 Сбросить всё", "callback_data": "action:reset_all"},
            ],
            [
                {"text": "⬅️ Назад", "callback_data": "ui:main"},
            ],
        ]
    }
