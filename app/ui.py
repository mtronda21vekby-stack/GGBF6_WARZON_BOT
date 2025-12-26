# -*- coding: utf-8 -*-
import random
from typing import Dict, Any

from app.state import ensure_profile, ensure_daily, USER_STATS, USER_MEMORY

THINKING_LINES = ["🧠 Думаю…", "⌛ Секунду…", "🎮 Окей, ща разложу…", "🌑 Анализирую…"]

CAUSE_LABEL = {
    "info": "Инфо (звук/радар/пинги)",
    "timing": "Тайминг (когда пикнул/вышел)",
    "position": "Позиция (угол/высота/линия обзора)",
    "discipline": "Дисциплина (жадность/ресурсы/ресет)",
    "mechanics": "Механика (аим/отдача/сенса)",
}

def thinking_line() -> str:
    return random.choice(THINKING_LINES)

def _badge(ok: bool) -> str:
    return "✅" if ok else "🚫"

def header(chat_id: int, ai_enabled: bool, model_name: str) -> str:
    p = ensure_profile(chat_id)
    ai = "ON" if ai_enabled else "OFF"
    return f"🌑 FPS Coach Bot v2 | 🎮 {p.get('game','auto').upper()} | 🔁 {p.get('mode','chat').upper()} | 🤖 AI {ai}"

def main_text(chat_id: int, ai_enabled: bool, model_name: str) -> str:
    p = ensure_profile(chat_id)
    mode = p.get("mode", "chat")
    if mode == "chat":
        return (
            f"{header(chat_id, ai_enabled, model_name)}\n\n"
            "Напиши как другу/тиммейту: что бесит, где умираешь, что хочешь улучшить.\n"
            "Я буду задавать вопросы и вести тебя к решению.\n\n"
            "Или жми меню 👇"
        )
    return (
        f"{header(chat_id, ai_enabled, model_name)}\n\n"
        "COACH режим: опиши 1 сцену:\n"
        "• где был • кто первый увидел • на чём умер • что хотел сделать\n\n"
        "Или жми меню 👇"
    )

def help_text() -> str:
    return (
        "❓ Помощь\n"
        "Режимы:\n"
        "• CHAT — живой разговор/вопросы/разбор по шагам\n"
        "• COACH — структурный разбор (4 блока)\n\n"
        "Команды:\n"
        "/start /menu\n"
        "/profile\n"
        "/daily\n"
        "/zombies\n"
        "/reset\n"
    )

def status_text(model_name: str, data_dir: str, ai_enabled: bool) -> str:
    return (
        "🧾 Статус\n"
        f"OPENAI_MODEL: {model_name}\n"
        f"DATA_DIR: {data_dir}\n"
        f"ИИ: {'ON' if ai_enabled else 'OFF'}\n"
        "Если Conflict 409 — у тебя два инстанса или где-то ещё включён getUpdates.\n"
    )

def profile_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    st = USER_STATS.get(chat_id, {})
    mem_len = len(USER_MEMORY.get(chat_id, []))
    daily = ensure_daily(chat_id)

    top = sorted(st.items(), key=lambda kv: kv[1], reverse=True)[:3]

    lines = [
        "📊 Профиль",
        f"Режим: {p.get('mode','chat').upper()}",
        f"Игра: {p.get('game','auto').upper()}",
        f"Стиль: {p.get('persona')}",
        f"Длина: {p.get('verbosity')}",
        f"Молния: {('ВКЛ' if p.get('speed','normal')=='lightning' else 'ВЫКЛ')}",
        f"Память: {p.get('memory','on').upper()} (сообщений: {mem_len})",
        "",
        "🧩 Карта проблем (топ):"
    ]
    if not top:
        lines.append("— пока пусто (нужны ситуации/смерти).")
    else:
        for c, n in top:
            lines.append(f"• {CAUSE_LABEL.get(c,c)}: {n}")

    lines += [
        "",
        "🎯 Задание дня:",
        f"• {daily.get('text')}",
        f"• сделано={daily.get('done',0)} / не вышло={daily.get('fail',0)}",
    ]
    return "\n".join(lines)

# -------------------------
# MENUS (INLINE)
# -------------------------
def menu_main(chat_id: int, ai_enabled: bool):
    p = ensure_profile(chat_id)
    game = p.get("game", "auto").upper()
    persona = p.get("persona", "spicy")
    talk = p.get("verbosity", "normal")
    mem_on = (p.get("memory", "on") == "on")
    mode = p.get("mode", "chat").upper()
    lightning_on = (p.get("speed", "normal") == "lightning")
    ai = "ON" if ai_enabled else "OFF"

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
                {"text": f"⚡ Молния: {'ВКЛ' if lightning_on else 'ВЫКЛ'}", "callback_data": "toggle:lightning"},
                {"text": "🧟 Zombies", "callback_data": "zmb:home"},
            ],
            [
                {"text": "📦 Ещё", "callback_data": "nav:more"},
            ],
        ]
    }

def menu_more(chat_id: int):
    return {"inline_keyboard": [
        [{"text": "🎛️ Настройки игры (WZ/BF6/BO7)", "callback_data": "action:game_settings"}],
        [{"text": "💪 Тренировка", "callback_data": "nav:training"}],
        [{"text": "🎯 Задание дня", "callback_data": "action:daily"}],
        [{"text": "📼 VOD-разбор", "callback_data": "action:vod"}],
        [{"text": "📊 Профиль", "callback_data": "action:profile"}],
        [{"text": "⚙️ Настройки бота", "callback_data": "nav:settings"}],
        [{"text": "🧽 Очистить память", "callback_data": "action:clear_memory"}],
        [{"text": "🧨 Сбросить всё", "callback_data": "action:reset_all"}],
        [{"text": "⬅️ Назад", "callback_data": "nav:main"}],
    ]}

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
        [{"text": "🎯 Задание дня", "callback_data": "action:daily"},
         {"text": "📼 VOD-разбор", "callback_data": "action:vod"}],
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
