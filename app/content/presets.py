# app/content/presets.py  (НОВЫЙ ФАЙЛ — минимальные пресеты, расширим)
from __future__ import annotations

# ЯЗЫК:
# - BF6 SETTINGS: ENGLISH
# - Warzone/BO7 SETTINGS: РУССКИЙ

PRESETS = {
    "warzone": {
        "normal": {
            "pc": {"title": "Warzone • ПК • Обычный", "settings": {"Мышь": {"DPI": "800", "Чувствительность": "6.0"}, "Обзор": {"FOV": "110"}}},
            "ps": {"title": "Warzone • PlayStation • Обычный", "settings": {"Контроллер": {"Deadzone": "0.02", "Кривая": "Dynamic"}, "Обзор": {"FOV": "110"}}},
            "xbox": {"title": "Warzone • Xbox • Обычный", "settings": {"Контроллер": {"Deadzone": "0.02", "Кривая": "Dynamic"}, "Обзор": {"FOV": "110"}}},
        },
        "pro": {
            "pc": {"title": "Warzone • ПК • Профи", "settings": {"Мышь": {"DPI": "800", "Чувствительность": "5.0"}, "Обзор": {"FOV": "115"}}},
            "ps": {"title": "Warzone • PlayStation • Профи", "settings": {"Контроллер": {"Deadzone": "0.01", "Кривая": "Dynamic"}, "Обзор": {"FOV": "115"}}},
            "xbox": {"title": "Warzone • Xbox • Профи", "settings": {"Контроллер": {"Deadzone": "0.01", "Кривая": "Dynamic"}, "Обзор": {"FOV": "115"}}},
        },
        "demon": {
            "pc": {"title": "Warzone • ПК • Демон", "settings": {"Мышь": {"DPI": "800", "Чувствительность": "4.3"}, "Обзор": {"FOV": "110"}}},
            "ps": {"title": "Warzone • PlayStation • Демон", "settings": {"Контроллер": {"Deadzone": "0.00–0.02", "Кривая": "Dynamic"}, "Обзор": {"FOV": "120"}}},
            "xbox": {"title": "Warzone • Xbox • Демон", "settings": {"Контроллер": {"Deadzone": "0.00–0.02", "Кривая": "Dynamic"}, "Обзор": {"FOV": "120"}}},
        },
    },
    "bo7": {
        "normal": {
            "pc": {"title": "BO7 • ПК • Обычный", "settings": {"Мышь": {"DPI": "800", "Чувствительность": "6.0"}, "Обзор": {"FOV": "105–110"}}},
            "ps": {"title": "BO7 • PlayStation • Обычный", "settings": {"Контроллер": {"Deadzone": "Низкий"}, "Обзор": {"FOV": "105–110"}}},
            "xbox": {"title": "BO7 • Xbox • Обычный", "settings": {"Контроллер": {"Deadzone": "Низкий"}, "Обзор": {"FOV": "105–110"}}},
        },
        "pro": {
            "pc": {"title": "BO7 • ПК • Профи", "settings": {"Мышь": {"DPI": "800", "Чувствительность": "5.0"}, "Обзор": {"FOV": "110"}}},
            "ps": {"title": "BO7 • PlayStation • Профи", "settings": {"Контроллер": {"Deadzone": "Очень низкий"}, "Обзор": {"FOV": "110"}}},
            "xbox": {"title": "BO7 • Xbox • Профи", "settings": {"Контроллер": {"Deadzone": "Очень низкий"}, "Обзор": {"FOV": "110"}}},
        },
        "demon": {
            "pc": {"title": "BO7 • ПК • Демон", "settings": {"Мышь": {"DPI": "800", "Чувствительность": "4.3"}, "Обзор": {"FOV": "110"}}},
            "ps": {"title": "BO7 • PlayStation • Демон", "settings": {"Контроллер": {"Deadzone": "Минимум без дрифта"}, "Обзор": {"FOV": "110"}}},
            "xbox": {"title": "BO7 • Xbox • Демон", "settings": {"Контроллер": {"Deadzone": "Минимум без дрифта"}, "Обзор": {"FOV": "110"}}},
        },
    },
    "bf6": {
        "normal": {
            "pc": {"title": "BF6 • PC (KBM) • Normal", "settings": {"Mouse": {"DPI": "800", "In-game Sens": "6.0"}, "Camera": {"FOV": "100–105"}}},
            "ps": {"title": "BF6 • PlayStation (Controller) • Normal", "settings": {"Controller": {"Deadzone L": "5", "Deadzone R": "5"}, "Camera": {"FOV": "100"}}},
            "xbox": {"title": "BF6 • Xbox (Controller) • Normal", "settings": {"Controller": {"Deadzone L": "5", "Deadzone R": "5"}, "Camera": {"FOV": "100"}}},
        },
        "pro": {
            "pc": {"title": "BF6 • PC (KBM) • Pro", "settings": {"Mouse": {"DPI": "800", "In-game Sens": "5.0"}, "Camera": {"FOV": "105"}}},
            "ps": {"title": "BF6 • PlayStation (Controller) • Pro", "settings": {"Controller": {"Deadzone L": "3", "Deadzone R": "3"}, "Camera": {"FOV": "105"}}},
            "xbox": {"title": "BF6 • Xbox (Controller) • Pro", "settings": {"Controller": {"Deadzone L": "3", "Deadzone R": "3"}, "Camera": {"FOV": "105"}}},
        },
        "demon": {
            "pc": {"title": "BF6 • PC (KBM) • Demon", "settings": {"Mouse": {"DPI": "800", "In-game Sens": "4.3"}, "Camera": {"FOV": "105
