from __future__ import annotations

# ВАЖНО:
# - Warzone/BO7 SETTINGS -> RU
# - BF6 SETTINGS -> EN

PRESETS = {
    "warzone": {
        "normal": {
            "pc": {
                "title": "Warzone • ПК (Клава+Мышь) • Обычный",
                "settings": {
                    "Мышь": {
                        "DPI": "800",
                        "Чувствительность в игре": "6.0",
                        "Множитель ADS": "1.00",
                        "Сглаживание мыши": "Выкл",
                    },
                    "Камера/обзор": {
                        "FOV": "110",
                        "FOV при прицеливании": "Зависит от настроек (Affected)",
                        "FOV оружия": "Широкий (Wide)",
                    },
                    "Звук": {
                        "Микс": "Наушники (Headphones)",
                        "Громкость эффектов": "Высоко",
                    },
                },
            },
            "ps": {
                "title": "Warzone • PlayStation • Обычный",
                "settings": {
                    "Контроллер": {
                        "Вибрация": "Выкл",
                        "Deadzone левый стик (мин)": "0.02",
                        "Deadzone правый стик (мин)": "0.02",
                    },
                    "Прицеливание": {
                        "Aim Assist": "Вкл",
                        "Тип помощи": "Стандарт",
                        "Кривая отклика": "Dynamic",
                        "Переход ADS": "Instant",
                        "ADS множитель (низкий зум)": "0.85",
                        "ADS множитель (высокий зум)": "1.00",
                    },
                    "Обзор": {"FOV": "110", "ADS FOV": "Affected", "Weapon FOV": "Wide"},
                },
            },
            "xbox": {
                "title": "Warzone • Xbox • Обычный",
                "settings": {
                    "Контроллер": {
                        "Вибрация": "Выкл",
                        "Deadzone левый стик (мин)": "0.02",
                        "Deadzone правый стик (мин)": "0.02",
                    },
                    "Прицеливание": {
                        "Aim Assist": "Вкл",
                        "Тип помощи": "Стандарт",
                        "Кривая отклика": "Dynamic",
                        "Переход ADS": "Instant",
                        "ADS множитель (низкий зум)": "0.85",
                        "ADS множитель (высокий зум)": "1.00",
                    },
                    "Обзор": {"FOV": "110", "ADS FOV": "Affected", "Weapon FOV": "Wide"},
                },
            },
        },
        "pro": {
            "pc": {
                "title": "Warzone • ПК (Клава+Мышь) • Профи",
                "settings": {
                    "Мышь": {"DPI": "800", "Чувствительность в игре": "5.0", "Множитель ADS": "0.90"},
                    "Камера/обзор": {"FOV": "110", "ADS FOV": "Affected", "FOV оружия": "Wide"},
                    "Звук": {"Микс": "Наушники", "Динамический диапазон": "Narrow/Low"},
                },
            },
            "ps": {
                "title": "Warzone • PlayStation • Профи",
                "settings": {
                    "Контроллер": {"Вибрация": "Выкл", "Deadzone L(min)": "0.01", "Deadzone R(min)": "0.01"},
                    "Прицеливание": {
                        "Aim Assist": "Вкл",
                        "Кривая": "Dynamic",
                        "ADS Low": "0.80",
                        "ADS High": "0.95",
                        "Переход ADS": "Instant",
                    },
                    "Обзор": {"FOV": "115", "ADS FOV": "Affected", "Weapon FOV": "Wide"},
                },
            },
            "xbox": {
                "title": "Warzone • Xbox • Профи",
                "settings": {
                    "Контроллер": {"Вибрация": "Выкл", "Deadzone L(min)": "0.01", "Deadzone R(min)": "0.01"},
                    "Прицеливание": {
                        "Aim Assist": "Вкл",
                        "Кривая": "Dynamic",
                        "ADS Low": "0.80",
                        "ADS High": "0.95",
                        "Переход ADS": "Instant",
                    },
                    "Обзор": {"FOV": "115", "ADS FOV": "Affected", "Weapon FOV": "Wide"},
                },
            },
        },
        "demon": {
            "pc": {
                "title": "Warzone • ПК (Клава+Мышь) • Демонический",
                "settings": {
                    "Мышь": {"DPI": "800", "Чувствительность в игре": "4.3", "Множитель ADS": "0.85"},
                    "Камера/обзор": {"FOV": "110", "ADS FOV": "Affected", "FOV оружия": "Wide"},
                    "Примечание": {"Важно": "Демонический тир = стабильность. Лучше ниже сенса, но больше коврик."},
                },
            },
            "ps": {
                "title": "Warzone • PlayStation • Демонический",
                "settings": {
                    "Контроллер": {"Вибрация": "Выкл", "Deadzone L(min)": "0.00–0.02", "Deadzone R(min)": "0.00–0.02"},
                    "Прицеливание": {"Aim Assist": "Вкл", "Кривая": "Dynamic", "ADS Low": "0.75", "ADS High": "0.90"},
                    "Обзор": {"FOV": "120", "ADS FOV": "Affected", "Weapon FOV": "Wide"},
                },
            },
            "xbox": {
                "title": "Warzone • Xbox • Демонический",
                "settings": {
                    "Контроллер": {"Вибрация": "Выкл", "Deadzone L(min)": "0.00–0.02", "Deadzone R(min)": "0.00–0.02"},
                    "Прицеливание": {"Aim Assist": "Вкл", "Кривая": "Dynamic", "ADS Low": "0.75", "ADS High": "0.90"},
                    "Обзор": {"FOV": "120", "ADS FOV": "Affected", "Weapon FOV": "Wide"},
                },
            },
        },
    },

    "bo7": {
        "normal": {
            "pc": {"title": "BO7 • ПК • Обычный", "settings": {"Мышь": {"DPI": "800", "Чувствительность": "6.0"}, "Обзор": {"FOV": "105–110"}}},
            "ps": {"title": "BO7 • PlayStation • Обычный", "settings": {"Контроллер": {"Вибрация": "Выкл", "Deadzone": "Низкий"}, "Обзор": {"FOV": "105–110"}}},
            "xbox": {"title": "BO7 • Xbox • Обычный", "settings": {"Контроллер": {"Вибрация": "Выкл", "Deadzone": "Низкий"}, "Обзор": {"FOV": "105–110"}}},
        },
        "pro": {
            "pc": {"title": "BO7 • ПК • Профи", "settings": {"Мышь": {"DPI": "800", "Чувствительность": "5.0"}, "Обзор": {"FOV": "110"}}},
            "ps": {"title": "BO7 • PlayStation • Профи", "settings": {"Контроллер": {"Deadzone": "Очень низкий"}, "Обзор": {"FOV": "110"}}},
            "xbox": {"title": "BO7 • Xbox • Профи", "settings": {"Контроллер": {"Deadzone": "Очень низкий"}, "Обзор": {"FOV": "110"}}},
        },
        "demon": {
            "pc": {"title": "BO7 • ПК • Демонический", "settings": {"Мышь": {"DPI": "800", "Чувствительность": "4.3"}, "Обзор": {"FOV": "110"}}},
            "ps": {"title": "BO7 • PlayStation • Демонический", "settings": {"Контроллер": {"Deadzone": "Минимально без дрифта"}, "Обзор": {"FOV": "110"}}},
            "xbox": {"title": "BO7 • Xbox • Демонический", "settings": {"Контроллер": {"Deadzone": "Минимально без дрифта"}, "Обзор": {"FOV": "110"}}},
        },
    },

    "bf6": {
        # BF6 SETTINGS MUST BE ENGLISH ONLY
        "normal": {
            "pc": {
                "title": "BF6 • PC (KBM) • Normal",
                "settings": {
                    "Mouse": {"DPI": "800", "In-game Sens": "6.0", "ADS Multiplier": "1.00"},
                    "Video/Camera": {"FOV": "100–105", "Motion Blur": "Off"},
                    "Audio": {"Mix": "Headphones", "Dynamic Range": "Low"},
                },
            },
            "ps": {
                "title": "BF6 • PlayStation (Controller) • Normal",
                "settings": {
                    "Controller": {"Vibration": "Off", "Left Stick Deadzone": "5", "Right Stick Deadzone": "5"},
                    "Aim": {"Aim Assist": "On", "Response Curve": "Standard"},
                    "Camera": {"FOV": "100"},
                },
            },
            "xbox": {
                "title": "BF6 • Xbox (Controller) • Normal",
                "settings": {
                    "Controller": {"Vibration": "Off", "Left Stick Deadzone": "5", "Right Stick Deadzone": "5"},
                    "Aim": {"Aim Assist": "On", "Response Curve": "Standard"},
                    "Camera": {"FOV": "100"},
                },
            },
        },
        "pro": {
            "pc": {
                "title": "BF6 • PC (KBM) • Pro",
                "settings": {
                    "Mouse": {"DPI": "800", "In-game Sens": "5.0", "ADS Multiplier": "0.90"},
                    "Video/Camera": {"FOV": "105", "Motion Blur": "Off"},
                    "Audio": {"Mix": "Headphones", "Dynamic Range": "Low"},
                },
            },
            "ps": {
                "title": "BF6 • PlayStation (Controller) • Pro",
                "settings": {
                    "Controller": {"Vibration": "Off", "Left Stick Deadzone": "3", "Right Stick Deadzone": "3"},
                    "Aim": {"Aim Assist": "On", "Response Curve": "Linear/Dynamic"},
                    "Camera": {"FOV": "105"},
                },
            },
            "xbox": {
                "title": "BF6 • Xbox (Controller) • Pro",
                "settings": {
                    "Controller": {"Vibration": "Off", "Left Stick Deadzone": "3", "Right Stick Deadzone": "3"},
                    "Aim": {"Aim Assist": "On", "Response Curve": "Linear/Dynamic"},
                    "Camera": {"FOV": "105"},
                },
            },
        },
        "demon": {
            "pc": {
                "title": "BF6 • PC (KBM) • Demon",
                "settings": {
                    "Mouse": {"DPI": "800", "In-game Sens": "4.3", "ADS Multiplier": "0.85"},
                    "Video/Camera": {"FOV": "105", "Motion Blur": "Off"},
                    "Notes": {"Tip": "Lower sens = better tracking; ensure enough mousepad space."},
                },
            },
            "ps": {
                "title": "BF6 • PlayStation (Controller) • Demon",
                "settings": {
                    "Controller": {"Vibration": "Off", "Left Stick Deadzone": "2", "Right Stick Deadzone": "2"},
                    "Aim": {"Aim Assist": "On", "Response Curve": "Linear/Dynamic"},
                    "Camera": {"FOV": "105"},
                    "Notes": {"Tip": "If drift exists, increase deadzone by +1."},
                },
            },
            "xbox": {
                "title": "BF6 • Xbox (Controller) • Demon",
                "settings": {
                    "Controller": {"Vibration": "Off", "Left Stick Deadzone": "2", "Right Stick Deadzone": "2"},
                    "Aim": {"Aim Assist": "On", "Response Curve": "Linear/Dynamic"},
                    "Camera": {"FOV": "105"},
                    "Notes": {"Tip": "If drift exists, increase deadzone by +1."},
                },
            },
        },
    },
}
