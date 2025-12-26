# -*- coding: utf-8 -*-
from typing import Dict, Any
from app.state import ensure_profile

PERSONA_HINT = {"spicy": "Дерзко 😈", "chill": "Спокойно 😌", "pro": "Профи 🎯"}
VERB_HINT = {"short": "Коротко", "normal": "Норм", "talkative": "Подробно"}
GAME_HINT = {"auto": "AUTO", "warzone": "Warzone", "bf6": "BF6", "bo7": "BO7"}

# ===== Bottom (reply keyboard) labels =====
BTN_MENU = "📋 Меню"
BTN_SETTINGS = "⚙️ Настройки"
BTN_GAME = "🎮 Игра"
BTN_PERSONA = "🎭 Стиль"
BTN_TALK = "🗣 Ответ"
BTN_ZOMBIES = "🧟 Zombies"
BTN_DAILY = "🎯 Задание дня"
BTN_VOD = "🎬 VOD"
BTN_PROFILE = "👤 Профиль"
BTN_STATUS = "📡 Статус"
BTN_HELP = "🆘 Помощь"
BTN_CLEAR_MEM = "🧽 Очистить память"
BTN_RESET = "🧨 Сброс"

def bottom_keyboard(chat_id: int) -> Dict[str, Any]:
    """
    Быстрые кнопки снизу (ReplyKeyboardMarkup).
    Inline-клавиатуры под сообщениями это НЕ ломает:
    они остаются на тех сообщениях, где были прикреплены.
    """
    # можно в будущем делать разные раскладки под игры/режимы
    ensure_profile(chat_id)
    return {
        "keyboard": [
            [{"text": BTN_MENU}, {"text": BTN_SETTINGS}],
            [{"text": BTN_GAME}, {"text": BTN_PERSONA}, {"text": BTN_TALK}],
            [{"text": BTN_ZOMBIES}, {"text": BTN_DAILY}, {"text": BTN_VOD}],
            [{"text": BTN_PROFILE}, {"text": BTN_STATUS}, {"text": BTN_HELP}],
            [{"text": BTN_CLEAR_MEM}, {"text": BTN_RESET}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "input_field_placeholder": "Опиши ситуацию/смерть…",
    }

def _badge(ok: bool) -> str:
    return "✅" if ok else "❌"

def thinking_line() -> str:
    return "🧠 Анализирую..."

def main_text(chat_id: int, ai_enabled: bool, model: str) -> str:
    p = ensure_profile(chat_id)
    g = p.get("game", "auto")
    mode = p.get("mode", "chat")
    return (
        f"🌑 FPS Coach Bot v2 | 🎮 {GAME_HINT.get(g, g)} | 🔁 {mode.upper()} | 🤖 AI {'ON' if ai_enabled else 'OFF'}\n\n"
        "Напиши ситуацию/смерть — разберу.\n"
        "Или жми меню 👇"
    )

def help_text() -> str:
    return (
        "❓ Помощь\n"
        "Команды:\n"
        "• /start или /menu — меню\n"
        "• /zombies — Zombies\n"
        "• /daily — задание дня\n"
        "• /status — статус\n"
        "• /profile — профиль\n"
        "• /reset — сброс\n"
    )

def status_text(model: str, data_dir: str, ai_enabled: bool) -> str:
    return (
        "📡 Статус:\n"
        f"• AI: {'ON' if ai_enabled else 'OFF'}\n"
        f"• Model: {model}\n"
        f"• Data dir: {data_dir}\n"
    )

def profile_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    return (
        "👤 Профиль:\n"
        f"• game: {p.get('game','auto')}\n"
        f"• mode: {p.get('mode','chat')}\n"
        f"• persona: {p.get('persona','spicy')} ({PERSONA_HINT.get(p.get('persona','spicy'),'')})\n"
        f"• verbosity: {p.get('verbosity','normal')} ({VERB_HINT.get(p.get('verbosity','normal'),'')})\n"
        f"• memory: {_badge(p.get('memory','on')=='on')}\n"
        f"• speed: {p.get('speed','normal')}\n"
        f"• ui: {p.get('ui','show')}\n"
        f"• player_level: {p.get('player_level','normal')}\n"
        f"• wz_device: {p.get('wz_device','pad')} | wz_tier: {p.get('wz_tier','normal')}\n"
        f"• bf6_device: {p.get('bf6_device','pad')} | bf6_tier: {p.get('bf6_tier','normal')}\n"
        f"• bo7_device: {p.get('bo7_device','pad')} | bo7_tier: {p.get('bo7_tier','normal')}\n"
    )

# =========================
# INLINE MENUS (кнопки под сообщением)
# =========================

def menu_main(chat_id: int, ai_enabled: bool) -> Dict[str, Any]:
    p = ensure_profile(chat_id)
    game = p.get("game", "auto")
    persona = p.get("persona", "spicy")
    verbosity = p.get("verbosity", "normal")
    mem_on = (p.get("memory", "on") == "on")
    mode = p.get("mode", "chat")
    speed = p.get("speed", "normal")

    icon = ("😈" if persona == "spicy" else "😌" if persona == "chill" else "🎯")

    return {"inline_keyboard": [
        [{"text": f"🎮 Игра: {GAME_HINT.get(game, game)}", "callback_data": "nav:game"},
         {"text": f"🎭 Стиль: {persona} {icon}", "callback_data": "nav:persona"}],

        [{"text": f"🗣 Ответ: {verbosity}", "callback_data": "nav:talk"},
         {"text": f"🧠 Память {_badge(mem_on)}", "callback_data": "toggle:memory"}],

        [{"text": f"🔁 Режим: {mode.upper()}", "callback_data": "toggle:mode"},
         {"text": f"🤖 ИИ: {'ON' if ai_enabled else 'OFF'}", "callback_data": "action:ai_status"}],

        [{"text": f"⚡ Молния: {'ВКЛ' if speed == 'lightning' else 'ВЫКЛ'}", "callback_data": "toggle:lightning"},
         {"text": "🧟 Zombies", "callback_data": "zmb:home"}],

        [{"text": "⚙️ Настройки", "callback_data": "nav:settings"},
         {"text": "📦 Ещё", "callback_data": "nav:more"}],
    ]}

def menu_more(chat_id: int) -> Dict[str, Any]:
    return {"inline_keyboard": [
        [{"text": "🎬 VOD / Разбор", "callback_data": "action:vod"}],
        [{"text": "🎯 Задание дня", "callback_data": "action:daily"}],
        [{"text": "👤 Профиль", "callback_data": "action:profile"}],
        [{"text": "🧽 Очистить память", "callback_data": "action:clear_memory"}],
        [{"text": "🧨 Сброс всего", "callback_data": "action:reset_all"}],
        [{"text": "⬅️ Назад", "callback_data": "nav:main"}],
    ]}

def menu_game(chat_id: int) -> Dict[str, Any]:
    return {"inline_keyboard": [
        [{"text": "🎮 AUTO", "callback_data": "set:game:auto"}],
        [{"text": "🎮 Warzone", "callback_data": "set:game:warzone"}],
        [{"text": "🎮 BF6", "callback_data": "set:game:bf6"}],
        [{"text": "🎮 BO7", "callback_data": "set:game:bo7"}],
        [{"text": "⬅️ Назад", "callback_data": "nav:main"}],
    ]}

def menu_persona(chat_id: int) -> Dict[str, Any]:
    return {"inline_keyboard": [
        [{"text": "😈 spicy", "callback_data": "set:persona:spicy"}],
        [{"text": "😌 chill", "callback_data": "set:persona:chill"}],
        [{"text": "🎯 pro", "callback_data": "set:persona:pro"}],
        [{"text": "⬅️ Назад", "callback_data": "nav:main"}],
    ]}

def menu_talk(chat_id: int) -> Dict[str, Any]:
    return {"inline_keyboard": [
        [{"text": "🗣 short", "callback_data": "set:talk:short"}],
        [{"text": "🗣 normal", "callback_data": "set:talk:normal"}],
        [{"text": "🗣 talkative", "callback_data": "set:talk:talkative"}],
        [{"text": "⬅️ Назад", "callback_data": "nav:main"}],
    ]}

def menu_training(chat_id: int) -> Dict[str, Any]:
    return {"inline_keyboard": [
        [{"text": "🎯 Aim", "callback_data": "action:drill:aim"}],
        [{"text": "🔫 Recoil", "callback_data": "action:drill:recoil"}],
        [{"text": "🏃 Movement", "callback_data": "action:drill:movement"}],
        [{"text": "⬅️ Назад", "callback_data": "nav:main"}],
    ]}

def menu_settings(chat_id: int) -> Dict[str, Any]:
    p = ensure_profile(chat_id)
    ui = p.get("ui", "show")
    speed = p.get("speed", "normal")
    return {"inline_keyboard": [
        [{"text": "📡 Статус", "callback_data": "action:status"}],
        [{"text": "🎮 Настройки игр", "callback_data": "nav:settings_game"}],
        [{"text": f"🧩 UI: {'Показ' if ui == 'show' else 'Скрыт'}", "callback_data": "toggle:ui"}],
        [{"text": f"⚡ Молния: {'ВКЛ' if speed == 'lightning' else 'ВЫКЛ'}", "callback_data": "toggle:lightning"}],
        [{"text": "⬅️ Назад", "callback_data": "nav:main"}],
    ]}

def menu_daily(chat_id: int) -> Dict[str, Any]:
    return {"inline_keyboard": [
        [{"text": "✅ Сделал", "callback_data": "daily:done"},
         {"text": "❌ Не вышло", "callback_data": "daily:fail"}],
        [{"text": "⬅️ Назад", "callback_data": "nav:main"}],
    ]}

# =========================
# Настройки игр — выбор устройства
# =========================

def menu_settings_game(chat_id: int) -> Dict[str, Any]:
    return {"inline_keyboard": [
        [{"text": "⚙️ Warzone — настройки", "callback_data": "nav:wz_settings"}],
        [{"text": "⚙️ BO7 — настройки", "callback_data": "nav:bo7_settings"}],
        [{"text": "⚙️ BF6 — settings (EN)", "callback_data": "nav:bf6_settings"}],
        [{"text": "⬅️ Назад", "callback_data": "nav:settings"}],
    ]}

def menu_wz_device(chat_id: int) -> Dict[str, Any]:
    return {"inline_keyboard": [
        [{"text": "🎮 PS5 / Xbox (Controller)", "callback_data": "wzdev:pad"}],
        [{"text": "🖥 PC (Mouse & Keyboard)", "callback_data": "wzdev:mnk"}],
        [{"text": "⬅️ Назад", "callback_data": "nav:settings_game"}],
    ]}

def menu_bo7_device(chat_id: int) -> Dict[str, Any]:
    return {"inline_keyboard": [
        [{"text": "🎮 PS5 / Xbox (Controller)", "callback_data": "bo7dev:pad"}],
        [{"text": "🖥 PC (Mouse & Keyboard)", "callback_data": "bo7dev:mnk"}],
        [{"text": "⬅️ Назад", "callback_data": "nav:settings_game"}],
    ]}

def menu_bf6_device(chat_id: int) -> Dict[str, Any]:
    return {"inline_keyboard": [
        [{"text": "🎮 PS5 / Xbox (Controller)", "callback_data": "bf6dev:pad"}],
        [{"text": "🖥 PC (Mouse & Keyboard)", "callback_data": "bf6dev:mnk"}],
        [{"text": "⬅️ Back", "callback_data": "nav:settings_game"}],
    ]}
