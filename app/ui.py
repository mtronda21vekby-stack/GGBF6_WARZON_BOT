# app/ui.py
# -*- coding: utf-8 -*-

def _badge(ok: bool) -> str:
    return "✅" if ok else "🚫"


def main_menu_markup(profile: dict):
    """
    Главное меню (компактно):
    - верх: игра/стиль/ответ/память/режим/ИИ/молния/зомби
    - низ: одна большая кнопка "📦 Ещё" вместо кучи кнопок
    """
    game = (profile.get("game", "auto") or "auto").upper()
    persona = profile.get("persona", "spicy")
    talk = profile.get("verbosity", "normal")
    mem_on = (profile.get("memory", "on") == "on")
    mode = (profile.get("mode", "chat") or "chat").upper()
    ai_on = (profile.get("ai", "on") == "on")
    lightning_on = (profile.get("lightning", "off") == "on")

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
                {"text": f"🤖 ИИ: {'ON' if ai_on else 'OFF'}", "callback_data": "toggle:ai"},
            ],
            [
                {"text": f"⚡ Молния: {'ВКЛ' if lightning_on else 'ВЫКЛ'}", "callback_data": "toggle:lightning"},
                {"text": "🧟 Zombies", "callback_data": "zmb:home"},
            ],
            [
                {"text": "📦 Ещё", "callback_data": "nav:more"},
            ],
        ]
    }


def more_menu_markup(profile: dict):
    """Меню дополнительных кнопок (спрятано под 'Ещё')."""
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
                {"text": "⬅️ Назад", "callback_data": "nav:main"},
            ],
        ]
    }


def game_menu_markup(profile: dict):
    cur = profile.get("game", "auto")

    def b(key, label):
        return {"text": ("✅ " if cur == key else "") + label, "callback_data": f"set:game:{key}"}

    return {
        "inline_keyboard": [
            [b("auto", "АВТО"), b("warzone", "WZ"), b("bf6", "BF6"), b("bo7", "BO7")],
            [{"text": "⬅️ Назад", "callback_data": "nav:main"}],
        ]
    }


def persona_menu_markup(profile: dict):
    cur = profile.get("persona", "spicy")

    def b(key, label):
        return {"text": ("✅ " if cur == key else "") + label, "callback_data": f"set:persona:{key}"}

    return {
        "inline_keyboard": [
            [b("spicy", "Дерзко 😈"), b("chill", "Спокойно 🙂"), b("pro", "Профи 🧠")],
            [{"text": "⬅️ Назад", "callback_data": "nav:main"}],
        ]
    }


def talk_menu_markup(profile: dict):
    cur = profile.get("verbosity", "normal")

    def b(key, label):
        return {"text": ("✅ " if cur == key else "") + label, "callback_data": f"set:talk:{key}"}

    return {
        "inline_keyboard": [
            [b("short", "Коротко"), b("normal", "Норм"), b("talkative", "Подробно")],
            [{"text": "⬅️ Назад", "callback_data": "nav:main"}],
        ]
    }


def daily_menu_markup():
    return {
        "inline_keyboard": [
            [{"text": "✅ Сделал", "callback_data": "daily:done"},
             {"text": "❌ Не вышло", "callback_data": "daily:fail"}],
            [{"text": "⬅️ Назад", "callback_data": "nav:main"}],
        ]
    }
