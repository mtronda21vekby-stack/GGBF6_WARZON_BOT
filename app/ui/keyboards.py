# app/ui/keyboards.py

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
                    {"text": "⚙️ Настройки", "callback_data": "settings"},
                ],
            ]
        }

    @staticmethod
    def back() -> dict:
        return {
            "inline_keyboard": [
                [{"text": "⬅️ Назад", "callback_data": "back"}]
            ]
        }
