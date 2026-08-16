# -*- coding: utf-8 -*-
from __future__ import annotations

from app.ui.quickbar import _miniapp_button


def _keyboard(rows: list[list[dict]], placeholder: str) -> dict:
    return {
        "keyboard": rows,
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": placeholder[:64],
    }


def _text(label: str) -> dict:
    return {"text": label}


def kb_premium_bridge() -> dict:
    """Premium account bridge with status-first information hierarchy."""
    return _keyboard(
        [
            [_text("💳 Premium статус"), _text("🔗 Связать с сайтом")],
            [_text("🎙 Голос: Тиммейт/Коуч"), _text("😈 Режим мышления")],
            [_text("🎯 Тренировка: План"), _text("🎬 VOD: Разбор")],
            [_text("🧩 Настройки игры"), _text("🧠 Память: Статус")],
            [_text("🔓 Отвязать сайт"), _miniapp_button()],
            [_text("⬅️ Назад")],
        ],
        "Premium · аккаунт · интеллект",
    )


def kb_premium_unlink_confirm() -> dict:
    return _keyboard(
        [
            [_text("⚠️ Подтвердить отвязку")],
            [_text("Отмена")],
        ],
        "Подтверди или отмени отвязку",
    )
