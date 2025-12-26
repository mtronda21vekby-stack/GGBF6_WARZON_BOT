# -*- coding: utf-8 -*-
from typing import Dict, Any, Optional

from app.pro_settings import get_text as pro_get_text
from app.state import ensure_profile


def wz_menu_hub() -> Dict[str, Any]:
    return {"inline_keyboard": [
        [{"text": "⚙️ Настройки (девайс)", "callback_data": "wz:settings"}],
        [{"text": "🧙 Pro / Магические настройки", "callback_data": "wz:pro"}],
        [{"text": "🎮 Режимы / Стиль игры", "callback_data": "wz:modes"}],
        [{"text": "🧠 Мышление / Ошибки", "callback_data": "wz:mindset"}],
        [{"text": "⬅️ Назад", "callback_data": "nav:settings_game"}],
    ]}


def wz_menu_device() -> Dict[str, Any]:
    return {"inline_keyboard": [
        [{"text": "🎮 PS5 / Xbox (Controller)", "callback_data": "wz:dev:pad"}],
        [{"text": "🖥 PC (Mouse & Keyboard)", "callback_data": "wz:dev:mnk"}],
        [{"text": "⬅️ Назад", "callback_data": "wz:hub"}],
    ]}


def _wz_hub_text() -> str:
    return (
        "🎮 Warzone — HUB\n\n"
        "Выбери раздел:\n"
        "• Настройки (девайс)\n"
        "• Pro / Магические\n"
        "• Режимы / Стиль\n"
        "• Мышление / Ошибки\n"
    )


def _wz_pro_text() -> str:
    return (
        "🧙 Warzone — Pro / Магические настройки\n\n"
        "Это расширенный слой поверх базовых настроек.\n"
        "Выбери стиль игрока и я дам точные тюнинги:\n\n"
        "• Агро / пуш\n"
        "• Позиционка / контроль\n"
        "• Снайп / дальний контроль\n"
        "• Универсал\n\n"
        "Ниже кнопки — выбери профиль."
    )


def _wz_modes_text() -> str:
    return (
        "🎮 Warzone — Режимы / Стиль\n\n"
        "Выбери что тебе ближе (дам принципы + микро-правила):\n"
        "• Агро (пуш)\n"
        "• Позиционка\n"
        "• Снайп/овер\n"
        "• Соло / Дуо / Сквад\n"
    )


def _wz_mindset_text() -> str:
    return (
        "🧠 Warzone — Мышление / Ошибки\n\n"
        "Премиум-логика:\n"
        "1) Инфо → 2) Угол → 3) Тайминг → 4) Ресет → 5) Репозиция\n\n"
        "Частые смерти:\n"
        "• репик того же угла\n"
        "• выход без инфо\n"
        "• жадность (без ресета)\n"
        "• плохая линия прострела\n\n"
        "Напиши 1 смерть (где/как/кто первый увидел) — разберу."
    )


def wz_menu_pro_profiles() -> Dict[str, Any]:
    return {"inline_keyboard": [
        [{"text": "🔥 Агро / Пуш", "callback_data": "wz:pro:agro"}],
        [{"text": "🧊 Позиционка", "callback_data": "wz:pro:pos"}],
        [{"text": "🎯 Снайп / Даль", "callback_data": "wz:pro:sniper"}],
        [{"text": "⚖️ Универсал", "callback_data": "wz:pro:universal"}],
        [{"text": "⬅️ Назад", "callback_data": "wz:hub"}],
    ]}


def _pro_profile_text(profile: str) -> str:
    if profile == "agro":
        return (
            "🔥 Warzone — Pro: Агро/Пуш\n\n"
            "Фокус:\n"
            "• быстрый инфо-контакт\n"
            "• 1-й хит → репозиция\n"
            "• дофайты только с ресурсом\n\n"
            "Тюнинг:\n"
            "• ADS чуть ниже базовой\n"
            "• камера/тряску вниз\n"
            "• приоритет: стабильность трекинга\n\n"
            "Хочешь — скажи девайс (pad/mnk) и текущую сенсу."
        )
    if profile == "pos":
        return (
            "🧊 Warzone — Pro: Позиционка\n\n"
            "Фокус:\n"
            "• углы/высота/линия обзора\n"
            "• игра от инфо и тайминга\n"
            "• «не умирать бесплатно»\n\n"
            "Тюнинг:\n"
            "• чуть ниже sens, выше стабильность\n"
            "• FOV по трекингу\n"
        )
    if profile == "sniper":
        return (
            "🎯 Warzone — Pro: Снайп/Даль\n\n"
            "Фокус:\n"
            "• первый выстрел + смена позиции\n"
            "• контроль линий прострела\n"
            "• не репикать ту же точку\n\n"
            "Тюнинг:\n"
            "• ADS множитель 0.80–0.95\n"
            "• приоритет: микро-коррекции\n"
        )
    return (
        "⚖️ Warzone — Pro: Универсал\n\n"
        "Фокус:\n"
        "• баланс трекинга и флика\n"
        "• стабильность важнее скорости\n\n"
        "Тюнинг:\n"
        "• базовые + маленькие правки под комфорт\n"
    )


def handle_callback(data: str) -> Optional[Dict[str, Any]]:
    if not data.startswith("wz:"):
        return None

    # Страница Warzone (для будущих быстрых команд текстом)
    out: Dict[str, Any] = {"set_profile": {"page": "warzone"}}

    if data == "wz:hub":
        out.update({"text": _wz_hub_text(), "reply_markup": wz_menu_hub()})
        return out

    if data == "wz:settings":
        out.update({"text": "⚙️ Warzone — выбери устройство:", "reply_markup": wz_menu_device()})
        return out

    if data.startswith("wz:dev:"):
        dev = data.split(":", 2)[2]  # pad/mnk
        key = f"wz:{'pad' if dev == 'pad' else 'mnk'}"
        out.update({"text": pro_get_text(key), "reply_markup": wz_menu_device()})
        return out

    if data == "wz:pro":
        out.update({"text": _wz_pro_text(), "reply_markup": wz_menu_pro_profiles()})
        return out

    if data.startswith("wz:pro:"):
        profile = data.split(":", 2)[2]
        out.update({"text": _pro_profile_text(profile), "reply_markup": wz_menu_pro_profiles()})
        return out

    if data == "wz:modes":
        out.update({"text": _wz_modes_text(), "reply_markup": wz_menu_hub()})
        return out

    if data == "wz:mindset":
        out.update({"text": _wz_mindset_text(), "reply_markup": wz_menu_hub()})
        return out

    # fallback
    out.update({"text": _wz_hub_text(), "reply_markup": wz_menu_hub()})
    return out
