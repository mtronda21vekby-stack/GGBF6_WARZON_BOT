from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def menu():
    kb = [
        [
            InlineKeyboardButton("💬 Чат", callback_data="mode:chat"),
            InlineKeyboardButton("🎯 Warzone Coach", callback_data="mode:coach"),
        ],
        [
            InlineKeyboardButton("🧟 Zombies", callback_data="mode:zombies"),
            InlineKeyboardButton("🧠 Очистить память", callback_data="mem:clear"),
        ],
        [
            InlineKeyboardButton("ℹ️ Помощь", callback_data="mode:help"),
        ],
    ]
    return InlineKeyboardMarkup(kb)