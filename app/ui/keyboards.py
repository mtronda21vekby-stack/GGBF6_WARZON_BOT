from __future__ import annotations


class KB:
    # ===== MAIN INLINE (как раньше) =====
    @staticmethod
    def main_inline() -> dict:
        return {
            "inline_keyboard": [
                [
                    {"text": "🎮 Игра: AUTO", "callback_data": "game:auto"},
                    {"text": "🎭 Стиль: spicy 😈", "callback_data": "style:spicy"},
                ],
                [
                    {"text": "💬 Ответ: normal", "callback_data": "answer:normal"},
                    {"text": "🧠 Память ✅", "callback_data": "mem:toggle"},
                ],
                [
                    {"text": "🔁 Режим: CHAT", "callback_data": "mode:chat"},
                    {"text": "🤖 ИИ: ON", "callback_data": "ai:toggle"},
                ],
                [
                    {"text": "⚡ Молния: ВЫКЛ", "callback_data": "bolt:off"},
                    {"text": "🧟 Zombies", "callback_data": "zombies:menu"},
                ],
                [
                    {"text": "⚙️ Настройки", "callback_data": "settings:menu"},
                    {"text": "📦 Ещё", "callback_data": "more:menu"},
                ],
            ]
        }

    # ===== SETTINGS (старое) =====
    @staticmethod
    def settings_device_wz() -> dict:
        return {
            "inline_keyboard": [
                [{"text": "🎮 PS5 / Xbox (Controller)", "callback_data": "wz_device:controller"}],
                [{"text": "🖥 PC (Mouse & Keyboard)", "callback_data": "wz_device:kbm"}],
                [{"text": "⬅️ Назад", "callback_data": "back:main"}],
            ]
        }

    # ===== SETTINGS (НОВОЕ: device) =====
    # Это то, что ты “остановился на 8 пункте”
    @staticmethod
    def settings_device(game=None) -> dict:
        # game пока не обязателен — оставили параметр для будущей логики
        return {
            "inline_keyboard": [
                [{"text": "🖥 PC (KBM)", "callback_data": "device:kbm"}],
                [{"text": "🎮 PS / Xbox", "callback_data": "device:pad"}],
                [{"text": "⬅️ Назад", "callback_data": "back:main"}],
            ]
        }

    # ===== SETTINGS (НОВОЕ: difficulty) =====
    @staticmethod
    def settings_difficulty() -> dict:
        return {
            "inline_keyboard": [
                [{"text": "🧠 Normal", "callback_data": "diff:normal"}],
                [{"text": "🔥 Pro", "callback_data": "diff:pro"}],
                [{"text": "😈 Demon", "callback_data": "diff:demon"}],
                [{"text": "⬅️ Назад", "callback_data": "back:main"}],
            ]
        }

    # ===== ZOMBIES (старое меню-заглушка, расширим позже) =====
    @staticmethod
    def zombies_menu() -> dict:
        return {
            "inline_keyboard": [
                [{"text": "🧟 Режим: BO7 Zombies", "callback_data": "zombies:bo7"}],
                [{"text": "🧟‍♂️ Режим: Zombie (расшир.)", "callback_data": "zombies:expanded"}],
                [{"text": "⬅️ Назад", "callback_data": "back:main"}],
            ]
        }

    # ===== MORE (старое) =====
    @staticmethod
    def more_menu() -> dict:
        return {
            "inline_keyboard": [
                [{"text": "🎯 Задание дня", "callback_data": "daily:task"}],
                [{"text": "🎬 VOD разбор", "callback_data": "vod:menu"}],
                [{"text": "⬅️ Назад", "callback_data": "back:main"}],
            ]
        }
