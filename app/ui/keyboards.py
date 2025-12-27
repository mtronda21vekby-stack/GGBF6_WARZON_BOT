from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu():
    kb = [
        [InlineKeyboardButton("🎮 Игра", callback_data="game"),
         InlineKeyboardButton("🎭 Стиль", callback_data="style")],
        [InlineKeyboardButton("🎯 Задание дня", callback_data="task"),
         InlineKeyboardButton("🎬 VOD", callback_data="vod")],
        [InlineKeyboardButton("👤 Профиль", callback_data="profile"),
         InlineKeyboardButton("🛰 Статус", callback_data="status")],
        [InlineKeyboardButton("🆘 Помощь", callback_data="help"),
         InlineKeyboardButton("🧹 Очистить память", callback_data="mem_clear")],
    ]
    return InlineKeyboardMarkup(kb)
