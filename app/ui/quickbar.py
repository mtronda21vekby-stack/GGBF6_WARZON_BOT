# app/ui/quickbar.py
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

def kb_main():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎮 Игра", callback_data="game"),
            InlineKeyboardButton("🎭 Стиль", callback_data="style"),
        ],
        [
            InlineKeyboardButton("🧠 ИИ", callback_data="ai"),
            InlineKeyboardButton("🧟 Zombies", callback_data="zombies"),
        ],
        [
            InlineKeyboardButton("⚙️ Настройки", callback_data="settings"),
            InlineKeyboardButton("📦 Ещё", callback_data="more"),
        ]
    ])

def kb_settings():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎮 Warzone", callback_data="set_wz"),
            InlineKeyboardButton("🪖 BF6", callback_data="set_bf6"),
        ],
        [
            InlineKeyboardButton("💻 PC", callback_data="pc"),
            InlineKeyboardButton("🎮 PS/Xbox", callback_data="console"),
        ],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="back"),
        ]
    ])