# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any, Mapping

VALID_BUTTON_STYLES = frozenset({"primary", "success", "danger"})
_ADVANCED_BUTTON_FIELDS = frozenset({"style", "icon_custom_emoji_id"})
_REPLY_ONLY_FIELDS = frozenset(
    {
        "request_users",
        "request_chat",
        "request_contact",
        "request_location",
        "request_poll",
    }
)
_INLINE_ACTION_FIELDS = frozenset(
    {
        "url",
        "callback_data",
        "web_app",
        "login_url",
        "switch_inline_query",
        "switch_inline_query_current_chat",
        "switch_inline_query_chosen_chat",
        "callback_game",
        "pay",
        "copy_text",
    }
)

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
    "◼ COMMAND CONSOLE": "primary",
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
    "‹",
    "⌂",
    "✕",
    "ℹ️",
    "Отмена",
    "CANCEL",
)
_DANGER_TERMS = (
    "сброс",
    "очистить",
    "отвяз",
    "unlink",
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
    "training",
    "premium статус",
    "premium active",
    "voice auto",
    "тиммейт",
    "teammate",
    "medic",
    "быстрые советы",
    "перки",
    "pack-a-punch",
)
_PRIMARY_PREFIXES = (
    "◼",
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


def _inline_navigation_enabled() -> bool:
    for name in ("TELEGRAM_AAA_CONSOLE_ENABLED", "TELEGRAM_INLINE_NAVIGATION"):
        value = (os.getenv(name) or "1").strip().casefold()
        if value in {"0", "false", "off", "no"}:
            return False
    return True


def _callback_value(text: str) -> str:
    value = str(text or "").strip()
    if not value or len(value.encode("utf-8")) > 64:
        return ""
    return value


def upgrade_reply_keyboard_to_inline(reply_markup: dict | None) -> dict | None:
    """
    Convert legacy ReplyKeyboardMarkup into an inline navigation surface.

    Existing labels become callback_data, so the legacy Router can continue to
    process them unchanged. Markups using contact/location/chat request fields
    remain native reply keyboards because those capabilities have no inline
    equivalent. `TELEGRAM_AAA_CONSOLE_ENABLED=0` is the emergency rollback.
    """
    if not isinstance(reply_markup, Mapping) or not _inline_navigation_enabled():
        return reply_markup
    if "keyboard" not in reply_markup or reply_markup.get("remove_keyboard"):
        return dict(reply_markup)

    rows = reply_markup.get("keyboard")
    if not isinstance(rows, list):
        return dict(reply_markup)

    converted: list[list[dict[str, Any]]] = []
    for row in rows:
        if not isinstance(row, list):
            return dict(reply_markup)
        inline_row: list[dict[str, Any]] = []
        for raw_button in row:
            if isinstance(raw_button, str):
                button: dict[str, Any] = {"text": raw_button}
            elif isinstance(raw_button, Mapping):
                button = dict(raw_button)
            else:
                return dict(reply_markup)

            if any(field in button for field in _REPLY_ONLY_FIELDS):
                return dict(reply_markup)

            text = str(button.get("text") or "").strip()
            if not text:
                return dict(reply_markup)

            has_action = any(field in button for field in _INLINE_ACTION_FIELDS)
            if not has_action:
                callback_data = _callback_value(text)
                if not callback_data:
                    return dict(reply_markup)
                button["callback_data"] = callback_data

            inline_row.append(button)
        if inline_row:
            converted.append(inline_row)

    return {"inline_keyboard": converted}


def decorate_reply_markup(reply_markup: dict | None) -> dict | None:
    """Add Bot API native styles without mutating caller-owned data."""
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
        rows = reply_markup.get(field)
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
