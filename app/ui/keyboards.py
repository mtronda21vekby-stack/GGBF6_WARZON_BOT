class KB:
    @staticmethod
    def main_menu() -> dict:
        return {
            "inline_keyboard": [
                [
                    {"text": "🎯 Тренировка", "callback_data": "train"},
                    {"text": "📊 Профиль", "callback_data": "profile"},
                ],
                [
                    {"text": "🧠 ИИ-режим", "callback_data": "ai_mode"},
                    {"text": "🧹 Очистить память", "callback_data": "mem_clear"},
                ],
            ]
        }

    @staticmethod
    def back() -> dict:
        return {"inline_keyboard": [[{"text": "⬅️ Назад", "callback_data": "back"}]]}
