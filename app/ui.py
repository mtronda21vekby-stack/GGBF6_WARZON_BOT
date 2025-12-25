# app/ui.py
# -*- coding: utf-8 -*-

def main_menu_markup():
    # пока минимально (чтобы всё работало)
    return {
        "inline_keyboard": [
            [
                {"text": "🧟 Zombies", "callback_data": "zmb:home"},
            ],
        ]
    }
