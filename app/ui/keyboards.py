from __future__ import annotations


class KB:
    @staticmethod
    def main_inline() -> dict:
        return {
            "inline_keyboard": [
                [{"text": "🎮 Игра: AUTO", "callback_data": "game:auto"},
                 {"text": "🎭 Стиль: spicy 😈", "callback_data": "style:spicy"}],
                [{"text": "💬 Ответ: normal", "callback_data": "answer:normal"},
                 {"text": "🧠 Память ✅", "callback_data": "mem:toggle"}],
                [{"text": "🔁 Режим: CHAT", "callback_data": "mode:chat"},
                 {"text": "🤖 ИИ: ON", "callback_data": "ai:toggle"}],
                [{"text": "⚡ Молния: ВЫКЛ", "callback_data": "bolt:off"},
                 {"text": "🧟 Zombies", "callback_data": "zombies:menu"}],
                [{"text": "⚙️ Настройки", "callback_data": "settings:menu"},
                 {"text": "📦 Ещё", "callback_data": "more:menu"}],
            ]
        }

    @staticmethod
    def settings_device_wz() -> dict:
        return {
            "inline_keyboard": [
                [{"text": "🎮 PS5 / Xbox (Controller)", "callback_data": "wz_device:controller"}],
                [{"text": "🖥 PC (Mouse & Keyboard)", "callback_data": "wz_device:kbm"}],
                [{"text": "⬅️ Назад", "callback_data": "back:main"}],
            ]
        }

    @staticmethod
    def zombies_menu() -> dict:
        return {
            "inline_keyboard": [
                [{"text": "🧟 Режим: BO7 Zombies", "callback_data": "zombies:bo7"}],
                [{"text": "🧟‍♂️ Режим: Zombie (расшир.)", "callback_data": "zombies:expanded"}],
                [{"text": "⬅️ Назад", "callback_data": "back:main"}],
            ]
        }

    @staticmethod
    def more_menu() -> dict:
        return {
            "inline_keyboard": [
                [{"text": "🎯 Задание дня", "callback_data": "daily:task"}],
                [{"text": "🎬 VOD разбор", "callback_data": "vod:menu"}],
                [{"text": "⬅️ Назад", "callback_data": "back:main"}],
            ]
        }
