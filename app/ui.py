# -*- coding: utf-8 -*-
from typing import Dict, Any
from app.state import ensure_profile

BTN_MENU = "📋 Меню"
BTN_SETTINGS = "⚙️ Настройки"
BTN_GAME = "🎮 Игра"
BTN_STYLE = "🎭 Стиль"
BTN_VERB = "🗣 Ответ"
BTN_ZOMBIES = "🧟 Zombies"
BTN_DAILY = "🎯 Задание дня"
BTN_VOD = "🎬 VOD"
BTN_PROFILE = "👤 Профиль"
BTN_STATUS = "📡 Статус"
BTN_HELP = "🆘 Помощь"
BTN_CLEAR = "🧽 Очистить память"
BTN_RESET = "🧨 Сброс"

def reply_keyboard() -> Dict[str, Any]:
    return {
        "keyboard": [
            [BTN_MENU, BTN_SETTINGS],
            [BTN_GAME, BTN_STYLE, BTN_VERB],
            [BTN_ZOMBIES, BTN_DAILY, BTN_VOD],
            [BTN_PROFILE, BTN_STATUS, BTN_HELP],
            [BTN_CLEAR, BTN_RESET],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "input_field_placeholder": "Опиши ситуацию/смерть…",
    }

def header(chat_id: int, ai_on: bool, model: str) -> str:
    p = ensure_profile(chat_id)
    return (
        f"🧠 Brain v3 | 🎮 {p.get('game','auto').upper()} | 🎭 {p.get('persona','spicy')} | "
        f"🗣 {p.get('verbosity','normal')} | 💾 {p.get('memory','on')} | 🤖 {'ON' if ai_on else 'OFF'}\n"
        f"Model: {model}"
    )

def menu_text(chat_id: int, ai_on: bool, model: str) -> str:
    return header(chat_id, ai_on, model) + "\n\nНапиши где умер и почему думаешь — разберу. Или жми кнопки снизу 👇"

def settings_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    return (
        "⚙️ Настройки\n"
        f"• game: {p.get('game')}\n"
        f"• persona: {p.get('persona')}\n"
        f"• verbosity: {p.get('verbosity')}\n"
        f"• memory: {p.get('memory')}\n"
        f"• mode: {p.get('mode')}\n"
        f"• player_level: {p.get('player_level')}\n\n"
        "Команды быстрые:\n"
        "• Игра: AUTO/WARZONE/BF6/BO7\n"
        "• Стиль: SPICY/CHILL/PRO\n"
        "• Ответ: SHORT/NORMAL/TALKATIVE\n"
        "• Память: ON/OFF"
    )

def profile_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    return (
        "👤 Профиль\n"
        f"game={p.get('game')} | persona={p.get('persona')} | verbosity={p.get('verbosity')}\n"
        f"memory={p.get('memory')} | mode={p.get('mode')} | level={p.get('player_level')}"
    )
