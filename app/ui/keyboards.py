# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Any, List

def _inline(rows: List[List[Dict[str, str]]]) -> Dict[str, Any]:
    return {"inline_keyboard": rows}

class KB:
    @staticmethod
    def main_menu() -> Dict[str, Any]:
        return _inline([
            [{"text": "📋 Меню", "callback_data": "menu"} , {"text": "⚙️ Настройки", "callback_data": "settings"}],
            [{"text": "🎮 Игра", "callback_data": "game"}, {"text": "🎭 Стиль", "callback_data": "style"}, {"text": "💬 Ответ", "callback_data": "answer"}],
            [{"text": "🧟 Zombies", "callback_data": "zombies"}, {"text": "🎯 Задание дня", "callback_data": "daily"}],
            [{"text": "🎬 VOD", "callback_data": "vod"}, {"text": "👤 Профиль", "callback_data": "profile"}, {"text": "📡 Статус", "callback_data": "status"}],
            [{"text": "🧠 Очистить память", "callback_data": "memory_clear"}, {"text": "🧨 Сброс", "callback_data": "reset"}],
        ])

    @staticmethod
    def settings() -> Dict[str, Any]:
        return _inline([
            [{"text": "🕒 Таймзона", "callback_data": "settings_tz"}],
            [{"text": "⬅️ Назад", "callback_data": "menu"}],
        ])

    @staticmethod
    def game_pick() -> Dict[str, Any]:
        return _inline([
            [{"text": "Warzone", "callback_data": "set_game:warzone"}, {"text": "BF6", "callback_data": "set_game:bf6"}],
            [{"text": "Zombies", "callback_data": "set_game:zombies"}],
            [{"text": "⬅️ Назад", "callback_data": "menu"}],
        ])

    @staticmethod
    def style_pick() -> Dict[str, Any]:
        return _inline([
            [{"text": "Коротко", "callback_data": "set_style:short"}, {"text": "Подробно", "callback_data": "set_style:long"}],
            [{"text": "Жёстко (coach)", "callback_data": "set_style:coach"}, {"text": "Дружелюбно", "callback_data": "set_style:friendly"}],
            [{"text": "⬅️ Назад", "callback_data": "menu"}],
        ])
