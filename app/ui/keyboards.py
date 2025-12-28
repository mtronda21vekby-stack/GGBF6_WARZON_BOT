class KB:
    @staticmethod
    def main_menu() -> dict:
        return {
            "inline_keyboard": [
                [{"text": "🎮 Режимы", "callback_data": "menu:modes"}],
                [{"text": "🧠 ИИ-режим", "callback_data": "ai_mode"}, {"text": "🧹 Очистить память", "callback_data": "mem_clear"}],
                [{"text": "📚 Классы BF6", "callback_data": "show:classes_bf6"}, {"text": "🧟 BO7 Zombies", "callback_data": "show:bo7_zombies"}]
            ]
        }

    @staticmethod
    def modes_menu() -> dict:
        return {
            "inline_keyboard": [
                [{"text": "Warzone", "callback_data": "pick_game:warzone"}],
                [{"text": "BF6", "callback_data": "pick_game:bf6"}],
                [{"text": "BO7", "callback_data": "pick_game:bo7"}],
                [{"text": "⬅️ Назад", "callback_data": "back:main"}]
            ]
        }

    @staticmethod
    def warzone_modes() -> dict:
        return {
            "inline_keyboard": [
                [{"text": "BR", "callback_data": "pick_mode:wz_br"}],
                [{"text": "Resurgence", "callback_data": "pick_mode:wz_resurgence"}],
                [{"text": "Ranked", "callback_data": "pick_mode:wz_ranked"}],
                [{"text": "⬅️ Назад", "callback_data": "menu:modes"}]
            ]
        }

    @staticmethod
    def device_menu() -> dict:
        return {
            "inline_keyboard": [
                [{"text": "KBM", "callback_data": "pick_device:kbm"}],
                [{"text": "PlayStation", "callback_data": "pick_device:ps"}],
                [{"text": "Xbox", "callback_data": "pick_device:xbox"}],
                [{"text": "⬅️ Назад", "callback_data": "menu:modes"}]
            ]
        }

    @staticmethod
    def tier_menu() -> dict:
        return {
            "inline_keyboard": [
                [{"text": "Обычный", "callback_data": "pick_tier:normal"}],
                [{"text": "Профи", "callback_data": "pick_tier:pro"}],
                [{"text": "Демонический", "callback_data": "pick_tier:demon"}],
                [{"text": "⬅️ Назад", "callback_data": "menu:modes"}]
            ]
        }

    @staticmethod
    def show_menu() -> dict:
        return {
            "inline_keyboard": [
                [{"text": "⚙️ Настройки", "callback_data": "show:settings"}],
                [{"text": "🎯 Тренировки", "callback_data": "show:training"}],
                [{"text": "⬅️ Назад", "callback_data": "menu:modes"}]
            ]
        }
