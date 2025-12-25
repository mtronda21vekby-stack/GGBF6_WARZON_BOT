# app/ui.py
# -*- coding: utf-8 -*-

def main_menu_markup():
    return {
        "inline_keyboard": [
            [
                {"text": "🎮 Игра: AUTO", "callback_data": "cfg:game"},
                {"text": "🎭 Стиль: spicy", "callback_data": "cfg:persona"},
            ],
            [
                {"text": "💬 Ответ: normal", "callback_data": "cfg:verbosity"},
                {"text": "✅ Память", "callback_data": "cfg:memory"},
            ],
            [
                {"text": "🔁 Режим: CHAT", "callback_data": "cfg:mode"},
                {"text": "🤖 ИИ: ON", "callback_data": "cfg:ai"},
            ],
            [
                {"text": "⚡ Молния: ВЫКЛ", "callback_data": "cfg:lightning"},
                {"text": "🧟 Zombies", "callback_data": "zombies:home"},
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
                {"text": "💪 Тренировка", "callback_data": "more:training"},
                {"text": "📊 Профиль", "callback_data": "more:profile"},
            ],
            [
                {"text": "⚙️ Настройки", "callback_data": "more:settings"},
                {"text": "🎯 Задание дня", "callback_data": "more:daily"},
            ],
            [
                {"text": "🧠 Очистить память", "callback_data": "more:clear_memory"},
                {"text": "🧨 Сбросить всё", "callback_data": "more:reset"},
            ],
            [
                {"text": "⬅️ Назад", "callback_data": "ui:main"},
            ],
        ]
    }
