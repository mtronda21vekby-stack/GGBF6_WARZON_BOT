# -*- coding: utf-8 -*-

def bf6_main_keyboard():
    # Кнопки СНИЗУ (ReplyKeyboardMarkup)
    return {
        "keyboard": [
            [{"text": "🎮 Как играть (BF6)"}],
            [{"text": "🧠 Мышление BF6"}, {"text": "💀 Почему умираю"}],
            [{"text": "🎯 Роль в команде"}],
            [{"text": "⚙️ Устройство: PC / PS5 / Xbox"}],
            [{"text": "⬅️ Назад (BF6)"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True
    }


def remove_reply_keyboard():
    return {"remove_keyboard": True}
