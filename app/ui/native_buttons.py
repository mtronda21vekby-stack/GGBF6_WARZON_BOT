# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any, Mapping

VALID_BUTTON_STYLES = frozenset({"primary", "success", "danger"})
_ADVANCED_BUTTON_FIELDS = frozenset({"style", "icon_custom_emoji_id"})

# Exact choices keep the primary product surface deliberate instead of relying
# only on broad keyword heuristics.
_EXACT_STYLES: dict[str, str | None] = {
    # Main command deck
    "🧠 ИИ": "primary",
    "🎯 Тренировка": "success",
    "🎮 Игра": "primary",
    "🎬 VOD": "success",
    "🧟 Zombies": "danger",
    "📌 Профиль": "primary",
    "💎 Premium": "success",
    "⚙️ Настройки": None,
    "📊 Статус": "primary",
    "🛰 COMMAND CENTER": "primary",
    "🛰 MINI APP": "primary",
    # Premium / account
    "💳 Premium статус": "success",
    "🔗 Связать с сайтом": "primary",
    "🔓 Отвязать сайт": "danger",
    "⚠️ Подтвердить отвязку": "danger",
    # Voice
    "🤝 Тиммейт": "success",
    "📚 Коуч": "primary",
    "🔇 Voice OFF": "danger",
    "🔊 Voice AUTO": "success",
    "🎧 Voice ON-DEMAND": "primary",
    "🔊 Озвучить ответ": "primary",
    # Difficulty / world selection
    "🧠 Normal": None,
    "🔥 Pro": "primary",
    "😈 Demon": "danger",
    "🔥 Warzone": "success",
    "💣 BO7": "primary",
    "🪖 BF6": "primary",
    # Guarded system actions
    "🧹 Очистить память": "danger",
    "🧨 Сброс": "danger",
    # Navigation must remain visually quiet.
    "⬅️ Назад": None,
    "⬅️ Back": None,
    "Отмена": None,
}

_NEUTRAL_PREFIXES = (
    "⬅️",
    "ℹ️",
    "Отмена",
)
_DANGER_TERMS = (
    "сброс",
    "очистить",
    "отвяз",
    "подтвердить отвязку",
    "voice off",
    "demon",
    "зомби",
    "zombies",
    "🧟",
    "💀",
)
_SUCCESS_TERMS = (
    "трениров",
    "premium статус",
    "voice auto",
    "тиммейт",
    "medic",
    "быстрые советы",
    "перки",
    "pack-a-punch",
)
_PRIMARY_PREFIXES = (
    "🧠",
    "🎮",
    "🎬",
    "📌",
    "💎",
    "📊",
    "🛰",
    "🗺",
    "🔗",
    "🎙",
    "⚡",
    "🎯",
    "🖥",
    "⌨️",
    "🔊",
    "🎥",
    "📄",
    "🔫",
    "🥚",
    "🧪",
    "🟥",
    "🟦",
    "🟨",
    "🟩",
)


def infer_button_style(text: str) -> str | None:
    """Return a native Telegram button style for one visible label."""
    label = str(text or "").strip()
    if not label:
        return None
    if label in _EXACT_STYLES:
        return _EXACT_STYLES[label]
    if label.startswith(_NEUTRAL_PREFIXES):
        return None

    lowered = label.casefold()
    if any(term in lowered for term in _DANGER_TERMS):
        return "danger"
    if any(term in lowered for term in _SUCCESS_TERMS):
        return "success"
    if label.startswith(_PRIMARY_PREFIXES):
        return "primary"
    return None


def _valid_custom_emoji_id(value: Any) -> str:
    icon_id = str(value or "").strip()
    if not icon_id or len(icon_id) > 32 or not icon_id.isdigit():
        return ""
    return icon_id


@lru_cache(maxsize=1)
def _custom_emoji_map() -> dict[str, str]:
    """
    Optional exact-label -> custom emoji ID map.

    Example:
      TELEGRAM_BUTTON_CUSTOM_EMOJI_JSON='{"COMMAND CENTER":"536832..."}'

    No custom emoji IDs are committed to source. Invalid values are ignored.
    """
    raw = (os.getenv("TELEGRAM_BUTTON_CUSTOM_EMOJI_JSON") or "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}

    result: dict[str, str] = {}
    for raw_label, raw_icon_id in list(payload.items())[:100]:
        label = str(raw_label or "").strip()[:64]
        icon_id = _valid_custom_emoji_id(raw_icon_id)
        if label and icon_id:
            result[label] = icon_id
    return result


def clear_native_button_cache() -> None:
    """Test/runtime hook for reloading optional emoji configuration."""
    _custom_emoji_map.cache_clear()


def _decorate_button(button: Any) -> Any:
    if isinstance(button, str):
        data: dict[str, Any] = {"text": button}
    elif isinstance(button, Mapping):
        data = dict(button)
    else:
        return button

    text = str(data.get("text") or "").strip()

    explicit_style = data.get("style")
    if explicit_style is not None and explicit_style not in VALID_BUTTON_STYLES:
        data.pop("style", None)
    if "style" not in data:
        inferred = infer_button_style(text)
        if inferred:
            data["style"] = inferred

    icon_id = _valid_custom_emoji_id(data.get("icon_custom_emoji_id"))
    if not icon_id:
        icon_id = _custom_emoji_map().get(text, "")
    if icon_id:
        data["icon_custom_emoji_id"] = icon_id
    else:
        data.pop("icon_custom_emoji_id", None)

    return data


def decorate_reply_markup(reply_markup: dict | None) -> dict | None:
    """Add Bot API 9.4+ native styles without mutating caller-owned data."""
    if not isinstance(reply_markup, Mapping):
        return reply_markup

    result = dict(reply_markup)
    for field in ("keyboard", "inline_keyboard"):
        rows = result.get(field)
        if not isinstance(rows, list):
            continue
        decorated_rows: list[list[Any]] = []
        for row in rows:
            if not isinstance(row, list):
                continue
            decorated_rows.append([_decorate_button(button) for button in row])
        result[field] = decorated_rows
    return result


def contains_advanced_button_fields(reply_markup: dict | None) -> bool:
    if not isinstance(reply_markup, Mapping):
        return False
    for field in ("keyboard", "inline_keyboard"):
        rows = reply_markup.get(field)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, list):
                continue
            for button in row:
                if isinstance(button, Mapping) and any(key in button for key in _ADVANCED_BUTTON_FIELDS):
                    return True
    return False


def strip_advanced_button_fields(reply_markup: dict | None) -> dict | None:
    """Compatibility fallback for an outdated self-hosted Bot API server."""
    if not isinstance(reply_markup, Mapping):
        return reply_markup

    result = dict(reply_markup)
    for field in ("keyboard", "inline_keyboard"):
        rows = result.get(field)
        if not isinstance(rows, list):
            continue
        clean_rows: list[list[Any]] = []
        for row in rows:
            if not isinstance(row, list):
                continue
            clean_row: list[Any] = []
            for button in row:
                if isinstance(button, Mapping):
                    clean_row.append(
                        {key: value for key, value in button.items() if key not in _ADVANCED_BUTTON_FIELDS}
                    )
                else:
                    clean_row.append(button)
            clean_rows.append(clean_row)
        result[field] = clean_rows
    return result
