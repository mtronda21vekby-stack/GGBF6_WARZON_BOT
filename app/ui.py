# app/ui.py
# -*- coding: utf-8 -*-

from app.state import ensure_profile

# callback_data (короткие и понятные)
CB_MORE_OPEN = "ui:more_open"
CB_MORE_CLOSE = "ui:more_close"

CB_GAME = "ui:game"
CB_STYLE = "ui:style"
CB_VERB = "ui:verb"
CB_MEM = "ui:mem"
CB_MODE = "ui:mode"
CB_AI = "ui:ai"
CB_LIGHT = "ui:light"

CB_TRAIN = "ui:train"
CB_PROFILE = "ui:profile"
CB_SETTINGS = "ui:settings"
CB_DAILY = "ui:daily"
CB_CLEAR_MEM = "ui:clear_mem"
CB_RESET = "ui:reset"

CB_ZOMBIES = "zombies:home"


def _label_game(v: str) -> str:
    v = (v or "auto").lower()
    return f"🎮 Игра: {v.upper()}"


def _label_style(v: str) -> str:
    v = (v or "spicy").lower()
    return f"🎭 Стиль: {v}"


def _label_verb(v: str) -> str:
    v = (v or "normal").lower()
    return f"💬 Ответ: {v}"


def _label_mem(v: str) -> str:
    return "✅ Память" if (v or "on") == "on" else "☑️ Память"


def _label_mode(v: str) -> str:
    v = (v or "chat").lower()
    return f"🔁 Режим: {v.upper()}"


def _label_ai(v: str) -> str:
    return "🤖 ИИ: ON" if (v or "on") == "on" else "🤖 ИИ: OFF"


def _label_light(v: str) -> str:
    return "⚡ Молния: ВКЛ" if (v or "off") == "on" else "⚡ Молния: ВЫКЛ"


def main_menu_markup(chat_id: int) -> dict:
    """
    Главное меню: только верхние кнопки + большая кнопка '📦 Ещё'.
    Все “нижние” кнопки доступны ТОЛЬКО внутри 'Ещё'.
    """
    p = ensure_profile(chat_id)

    kb = [
        [
            {"text": _label_game(p.get("game")), "callback_data": CB_GAME},
            {"text": _label_style(p.get("persona")), "callback_data": CB_STYLE},
        ],
        [
            {"text": _label_verb(p.get("verbosity")), "callback_data": CB_VERB},
            {"text": _label_mem(p.get("memory")), "callback_data": CB_MEM},
        ],
        [
            {"text": _label_mode(p.get("mode")), "callback_data": CB_MODE},
            {"text": _label_ai(p.get("ai", "on")), "callback_data": CB_AI},
        ],
        [
            {"text": _label_light(p.get("lightning")), "callback_data": CB_LIGHT},
            {"text": "🧟 Zombies", "callback_data": CB_ZOMBIES},
        ],
        [
            {"text": "📦 Ещё", "callback_data": CB_MORE_OPEN},
        ],
    ]

    return {"inline_keyboard": kb}


def more_menu_markup(chat_id: int) -> dict:
    """
    Меню 'Ещё' — тут живут кнопки, которые ты просил убрать вниз.
    """
    kb = [
        [
            {"text": "💪 Тренировка", "callback_data": CB_TRAIN},
            {"text": "📊 Профиль", "callback_data": CB_PROFILE},
        ],
        [
            {"text": "⚙️ Настройки", "callback_data": CB_SETTINGS},
            {"text": "🎯 Задание дня", "callback_data": CB_DAILY},
        ],
        [
            {"text": "🧹 Очистить память", "callback_data": CB_CLEAR_MEM},
            {"text": "🧨 Сбросить всё", "callback_data": CB_RESET},
        ],
        [
            {"text": "⬅️ Назад", "callback_data": CB_MORE_CLOSE},
        ],
    ]
    return {"inline_keyboard": kb}
