# app/ui/keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


class KB:
    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🎯 Тренировка", callback_data="train"),
                    InlineKeyboardButton("📊 Профиль", callback_data="profile"),
                ],
                [
                    InlineKeyboardButton("⚙️ Настройки", callback_data="settings"),
                ],
            ]
        )

    @staticmethod
    def back() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("⬅️ Назад", callback_data="back"),
                ]
            ]
        )
