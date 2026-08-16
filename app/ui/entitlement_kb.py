# -*- coding: utf-8 -*-
from __future__ import annotations

from app.ui.quickbar import _miniapp_button


def kb_premium_bridge() -> dict:
    return {
        "keyboard": [
            [{"text": "🔗 Связать с сайтом"}, {"text": "💳 Premium статус"}],
            [{"text": "🎙 Голос: Тиммейт/Коуч"}],
            [{"text": "😈 Режим мышления"}, {"text": "🧩 Настройки игры"}],
            [{"text": "🎯 Тренировка: План"}, {"text": "🎬 VOD: Разбор"}],
            [{"text": "🧠 Память: Статус"}, {"text": "🔓 Отвязать сайт"}],
            [_miniapp_button()],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Premium и связка аккаунтов…",
    }


def kb_premium_unlink_confirm() -> dict:
    return {
        "keyboard": [
            [{"text": "⚠️ Подтвердить отвязку"}],
            [{"text": "Отмена"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Подтверди или отмени отвязку…",
    }
