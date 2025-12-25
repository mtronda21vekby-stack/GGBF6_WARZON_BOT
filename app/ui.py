# app/ui.py
# -*- coding: utf-8 -*-

from app.state import ensure_profile
from app.ai import openai_client


def _badge(ok: bool) -> str:
    return "✅" if ok else "🚫"


def header(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    ai = "ON" if openai_client else "OFF"
    lightning = "⚡" if p.get("lightning") == "on" else ""
    return f"🌑 FPS Coach Bot v2 {lightning} | 🎮 {p.get('game','auto').upper()} | 🔁 {p.get('mode','chat').upper()} | 🤖 AI {ai}"


def main_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    if p.get("mode") == "coach":
        return (
            f"{header(chat_id)}\n\n"
            "COACH режим: опиши 1 сцену:\n"
            "• где был • кто первый увидел • на чём умер • что хотел сделать\n\n"
            "Или жми меню 👇"
        )
    return (
        f"{header(chat_id)}\n\n"
        "Напиши как другу/тиммейту: что бесит, где умираешь, что хочешь улучшить.\n"
        "Я буду задавать вопросы и вести тебя к решению.\n\n"
        "Или жми меню 👇"
    )


def menu_main(chat_id: int):
    p = ensure_profile(chat_id)
    if p.get("ui") == "hide":
        return None

    game = p.get("game", "auto").upper()
    persona = p.get("persona", "spicy")
    talk = p.get("verbosity", "normal")
    mem_on = (p.get("memory", "on") == "on")
    mode = p.get("mode", "chat").upper()
    ai = "ON" if openai_client else "OFF"
    lightning = "ВКЛ" if p.get("lightning") == "on" else "ВЫКЛ"

    # ✅ ОСТАВЛЯЕМ “Zombies” в главном меню
    # ❌ УБИРАЕМ нижние кнопки в “Ещё”
    return {
        "inline_keyboard": [
            [
                {"text": f"🎮 Игра: {game}", "callback_data": "nav:game"},
                {"text": f"🎭 Стиль: {persona}", "callback_data": "nav:persona"},
            ],
            [
                {"text": f"🗣 Ответ: {talk}", "callback_data": "nav:talk"},
                {"text": f"{_badge(mem_on)} Память", "callback_data": "toggle:memory"},
            ],
            [
                {"text": f"🔁 Режим: {mode}", "callback_data": "toggle:mode"},
                {"text": f"🤖 ИИ: {ai}", "callback_data": "action:ai_status"},
            ],
            [
                {"text": f"⚡ Молния: {lightning}", "callback_data": "toggle:lightning"},
                {"text": "🧟 Zombies", "callback_data": "zmb:home"},
            ],
            [
                {"text": "📦 Ещё", "callback_data": "nav:more"},
            ],
        ]
    }


def menu_more(chat_id: int):
    # ✅ Тут лежат все “нижние” кнопки
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


def menu_game(chat_id: int):
    p = ensure_profile(chat_id)
    cur = p.get("game", "auto")

    def b(key, label):
        return {"text": ("✅ " if cur == key else "") + label, "callback_data": f"set:game:{key}"}

    return {"inline_keyboard": [
        [b("auto", "АВТО"), b("warzone", "WZ"), b("bf6", "BF6"), b("bo7", "BO7")],
        [{"text": "⬅️ Назад", "callback_data": "nav:main"}]
    ]}


def menu_persona(chat_id: int):
    p = ensure_profile(chat_id)
    cur = p.get("persona", "spicy")

    def b(key, label):
        return {"text": ("✅ " if cur == key else "") + label, "callback_data": f"set:persona:{key}"}

    return {"inline_keyboard": [
        [b("spicy", "Дерзко 😈"), b("chill", "Спокойно 🙂"), b("pro", "Профи 🧠")],
        [{"text": "⬅️ Назад", "callback_data": "nav:main"}]
    ]}


def menu_talk(chat_id: int):
    p = ensure_profile(chat_id)
    cur = p.get("verbosity", "normal")

    def b(key, label):
        return {"text": ("✅ " if cur == key else "") + label, "callback_data": f"set:talk:{key}"}

    return {"inline_keyboard": [
        [b("short", "Коротко"), b("normal", "Норм"), b("talkative", "Подробно")],
        [{"text": "⬅️ Назад", "callback_data": "nav:main"}]
    ]}


def menu_training(chat_id: int):
    return {"inline_keyboard": [
        [{"text": "🎯 Аим", "callback_data": "action:drill:aim"},
         {"text": "🔫 Отдача", "callback_data": "action:drill:recoil"},
         {"text": "🕹 Мувмент", "callback_data": "action:drill:movement"}],
        [{"text": "⬅️ Назад", "callback_data": "nav:more"}],
    ]}


def menu_settings(chat_id: int):
    p = ensure_profile(chat_id)
    ui = p.get("ui", "show")
    return {"inline_keyboard": [
        [{"text": f"{_badge(ui=='show')} Показ меню", "callback_data": "toggle:ui"},
         {"text": "🧾 Статус", "callback_data": "action:status"}],
        [{"text": "⬅️ Назад", "callback_data": "nav:more"}],
    ]}


def menu_daily(chat_id: int):
    return {"inline_keyboard": [
        [{"text": "✅ Сделал", "callback_data": "daily:done"},
         {"text": "❌ Не вышло", "callback_data": "daily:fail"}],
        [{"text": "⬅️ Назад", "callback_data": "nav:more"}],
    ]}
