# app/ui/quickbar.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Iterable


# =========================
# MINI APP URL (Telegram WebApp)
# =========================
_BUILD_CACHE_VALUE: str | None = None
_BUILD_CACHE_AT: float = 0.0
_BUILD_CACHE_TTL_SEC = 2.0


def _static_dir() -> Path:
    """app/ui/quickbar.py -> app/webapp/static"""
    app_dir = Path(__file__).resolve().parents[1]
    return (app_dir / "webapp" / "static").resolve()


def _scan_static_mtime() -> int:
    static_dir = _static_dir()
    if not static_dir.exists():
        return int(time.time())

    newest = 0
    try:
        for path in static_dir.rglob("*"):
            if not path.is_file():
                continue
            try:
                newest = max(newest, int(path.stat().st_mtime))
            except Exception:
                continue
    except Exception:
        return int(time.time())

    return newest or int(time.time())


def _webapp_build() -> str:
    """Resolve a short cache-busting build id for Telegram iOS WebApp cache."""
    global _BUILD_CACHE_VALUE, _BUILD_CACHE_AT

    now = time.time()
    if _BUILD_CACHE_VALUE and (now - _BUILD_CACHE_AT) < _BUILD_CACHE_TTL_SEC:
        return _BUILD_CACHE_VALUE

    value = (os.getenv("WEBAPP_BUILD_ID") or "").strip()
    if not value:
        value = (os.getenv("RENDER_GIT_COMMIT") or "").strip()
    if not value:
        value = str(_scan_static_mtime())

    value = value[:12]
    _BUILD_CACHE_VALUE = value
    _BUILD_CACHE_AT = now
    return value


def _webapp_url() -> str:
    url = (os.getenv("WEBAPP_URL") or "").strip()
    if not url:
        base = (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
        url = f"{base}/webapp" if base else ""
    if not url:
        return ""

    build = _webapp_build().strip()
    if build:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}v={build}"
    return url


def _miniapp_button() -> dict:
    """Open the real Mini App when configured; keep the legacy text fallback."""
    url = _webapp_url()
    if url:
        return {"text": "🛰 COMMAND CENTER", "web_app": {"url": url}}
    return {"text": "🛰 MINI APP"}


# =========================
# KEYBOARD BUILDERS
# =========================
def _text_button(text: str) -> dict:
    return {"text": text}


def _row(*buttons: str | dict) -> list[dict]:
    result: list[dict] = []
    for button in buttons:
        result.append(button if isinstance(button, dict) else _text_button(button))
    return result


def _keyboard(rows: Iterable[list[dict]], *, placeholder: str = "Команда или ситуация…") -> dict:
    return {
        "keyboard": list(rows),
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": placeholder[:64],
    }


# =========================
# MAIN — TACTICAL COMMAND DECK
# =========================
def kb_main() -> dict:
    """Primary deck: frequent actions first, destructive actions are nested."""
    return _keyboard(
        [
            _row("🧠 ИИ", "🎯 Тренировка"),
            _row("🎮 Игра", "🎬 VOD"),
            _row("🧟 Zombies", "📌 Профиль"),
            _row("💎 Premium", "⚙️ Настройки"),
            _row("📊 Статус", _miniapp_button()),
        ],
        placeholder="Опиши файт: ситуация · ошибка · цель",
    )


# =========================
# PREMIUM HUB (legacy-compatible)
# =========================
def kb_premium() -> dict:
    return _keyboard(
        [
            _row("💳 Premium статус", "🔗 Связать с сайтом"),
            _row("🎙 Голос: Тиммейт/Коуч", "😈 Режим мышления"),
            _row("🎯 Тренировка: План", "🎬 VOD: Разбор"),
            _row("🧩 Настройки игры", "🧠 Память: Статус"),
            _row("🔓 Отвязать сайт", _miniapp_button()),
            _row("⬅️ Назад"),
        ],
        placeholder="Premium · аккаунт · интеллект",
    )


# =========================
# VOICE / PERSONA
# =========================
def kb_voice() -> dict:
    return _keyboard(
        [
            _row("🤝 Тиммейт", "📚 Коуч"),
            _row("⬅️ Назад"),
        ],
        placeholder="Выбери стиль ответа",
    )


# =========================
# SETTINGS / SYSTEM
# =========================
def kb_settings() -> dict:
    """Secondary deck with profile controls and guarded destructive actions."""
    return _keyboard(
        [
            _row("🎮 Выбрать игру", "🎭 Роль/Класс"),
            _row("🖥 Платформа", "⌨️ Input"),
            _row("😈 Режим мышления", "🎙 Голос: Тиммейт/Коуч"),
            _row("🧩 Настройки игры", "📊 Статус"),
            _row("🧹 Очистить память", "🧨 Сброс"),
            _row("⬅️ Назад"),
        ],
        placeholder="Настройки профиля и системы",
    )


def kb_games() -> dict:
    return _keyboard(
        [
            _row("🔥 Warzone", "💣 BO7"),
            _row("🪖 BF6"),
            _row("⬅️ Назад"),
        ],
        placeholder="Выбери игровой мир",
    )


def kb_platform() -> dict:
    return _keyboard(
        [
            _row("🖥 PC", "🎮 PlayStation"),
            _row("🎮 Xbox"),
            _row("⬅️ Назад"),
        ],
        placeholder="Выбери платформу",
    )


def kb_input() -> dict:
    return _keyboard(
        [
            _row("⌨️ KBM", "🎮 Controller"),
            _row("⬅️ Назад"),
        ],
        placeholder="Выбери устройство ввода",
    )


def kb_difficulty() -> dict:
    return _keyboard(
        [
            _row("🧠 Normal", "🔥 Pro"),
            _row("😈 Demon"),
            _row("⬅️ Назад"),
        ],
        placeholder="Глубина и жёсткость анализа",
    )


def kb_bf6_classes() -> dict:
    return _keyboard(
        [
            _row("🟥 Assault", "🟦 Recon"),
            _row("🟨 Engineer", "🟩 Medic"),
            _row("⬅️ Назад"),
        ],
        placeholder="Выбери класс BF6",
    )


def kb_roles() -> dict:
    return _keyboard(
        [
            _row("⚔️ Слэйер", "🚪 Энтри"),
            _row("🧠 IGL", "🛡 Саппорт"),
            _row("🌀 Флекс"),
            _row("⬅️ Назад"),
        ],
        placeholder="Выбери роль в отряде",
    )


def kb_game_settings_menu(game: str) -> dict:
    game_name = (game or "Warzone").strip()
    game_upper = game_name.upper()

    if game_upper == "BF6":
        return _keyboard(
            [
                _row("🪖 BF6: Class Settings", "🎯 BF6: Aim/Sens"),
                _row("🎮 BF6: Controller Tuning", "⌨️ BF6: KBM Tuning"),
                _row("⬅️ Назад"),
            ],
            placeholder="BF6 tactical settings",
        )

    if game_upper == "BO7":
        return _keyboard(
            [
                _row("🎭 BO7: Роль", "🎯 BO7: Aim/Sens"),
                _row("🎮 BO7: Controller", "⌨️ BO7: KBM"),
                _row("🧠 BO7: Мувмент/Позиционка", "🎧 BO7: Аудио/Видео"),
                _row("⬅️ Назад"),
            ],
            placeholder="Настройки BO7",
        )

    return _keyboard(
        [
            _row("🎭 Warzone: Роль", "🎯 Warzone: Aim/Sens"),
            _row("🎮 Warzone: Controller", "⌨️ Warzone: KBM"),
            _row("🧠 Warzone: Мувмент/Позиционка", "🎧 Warzone: Аудио/Видео"),
            _row("⬅️ Назад"),
        ],
        placeholder="Настройки Warzone",
    )


# =========================================================
# ZOMBIES — BACKWARD COMPATIBILITY
# =========================================================
def kb_zombies_home() -> dict:
    return _keyboard(
        [
            _row("🗺 Карты", "🧪 Перки"),
            _row("🔫 Оружие", "🥚 Пасхалки"),
            _row("🧠 Стратегия раундов", "⚡ Быстрые советы"),
            _row("⬅️ Назад"),
        ],
        placeholder="Zombies: карта · раунд · проблема",
    )


def kb_zombies_maps() -> dict:
    return _keyboard(
        [
            _row("🧟 Ashes", "🧟 Astra"),
            _row("⬅️ Назад"),
        ],
        placeholder="Выбери карту Zombies",
    )


def kb_zombies_sections() -> dict:
    return _keyboard(
        [
            _row("🚀 Старт/маршрут", "⚡ Pack-a-Punch"),
            _row("🔫 Чудо-оружие", "⚡ Перки (порядок)"),
            _row("🔫 Оружие (2 слота)", "🧠 Ротации/позиции"),
            _row("👹 Спец-зомби/боссы", "🧩 Пасхалка (основная)"),
            _row("🎁 Мини-пасхалки", "💀 Ошибки/вайпы"),
            _row("🧾 Чек-лист раунда", "🆘 Я застрял"),
            _row("⬅️ Назад"),
        ],
        placeholder="Выбери секцию Zombies",
    )
