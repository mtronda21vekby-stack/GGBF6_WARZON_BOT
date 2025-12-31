# app/ui/quickbar.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import time
from pathlib import Path


# =========================
# MINI APP URL (Telegram WebApp)
# =========================

# маленький кэш, чтобы не rglob на каждый апдейт (но почти realtime)
_BUILD_CACHE_VALUE: str | None = None
_BUILD_CACHE_AT: float = 0.0
_BUILD_CACHE_TTL_SEC = 2.0


def _static_dir() -> Path:
    """
    app/ui/quickbar.py -> app/webapp/static
    """
    app_dir = Path(__file__).resolve().parents[1]  # .../app
    return (app_dir / "webapp" / "static").resolve()


def _scan_static_mtime() -> int:
    """
    max mtime (секунды) по всем файлам в app/webapp/static/*
    Меняется при любом обновлении любого файла.
    """
    static_dir = _static_dir()
    if not static_dir.exists():
        return int(time.time())

    newest = 0
    try:
        for p in static_dir.rglob("*"):
            if p.is_file():
                try:
                    mt = int(p.stat().st_mtime)
                    if mt > newest:
                        newest = mt
                except Exception:
                    continue
    except Exception:
        return int(time.time())

    return newest or int(time.time())


def _webapp_build() -> str:
    """
    BUILD берём из:
      1) WEBAPP_BUILD_ID (ручной override)
      2) RENDER_GIT_COMMIT (Render deploy)
      3) max mtime по static/*
    """
    global _BUILD_CACHE_VALUE, _BUILD_CACHE_AT

    now = time.time()
    if _BUILD_CACHE_VALUE and (now - _BUILD_CACHE_AT) < _BUILD_CACHE_TTL_SEC:
        return _BUILD_CACHE_VALUE

    v = (os.getenv("WEBAPP_BUILD_ID") or "").strip()
    if not v:
        v = (os.getenv("RENDER_GIT_COMMIT") or "").strip()

    if not v:
        v = str(_scan_static_mtime())

    v = v[:12] if len(v) > 12 else v

    _BUILD_CACHE_VALUE = v
    _BUILD_CACHE_AT = now
    return v


def _webapp_url() -> str:
    """
    Берём URL мини-аппа из ENV:
      WEBAPP_URL=https://<host>/webapp
    Если не задан — пробуем собрать из PUBLIC_BASE_URL:
      PUBLIC_BASE_URL=https://<host>  -> /webapp

    ВАЖНО (Telegram iOS cache):
      добавляем авто cache-bust параметр v=BUILD
      BUILD = _webapp_build() (см. выше)
    """
    url = (os.getenv("WEBAPP_URL") or "").strip()
    if not url:
        base = (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
        url = (base + "/webapp") if base else ""

    if not url:
        return ""

    # всегда добавляем v=BUILD (если смогли получить build)
    build = _webapp_build().strip()
    if build:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}v={build}"

    return url


def _miniapp_button() -> dict:
    """
    Кнопка MINI APP:
    - если URL есть -> web_app кнопка
    - если URL нет -> обычная кнопка (не ломаем UI)
    """
    url = _webapp_url()
    if url:
        return {"text": "🛰 MINI APP", "web_app": {"url": url}}
    return {"text": "🛰 MINI APP"}


# =========================
# PREMIUM MAIN QUICKBAR (нижняя клавиатура)
# =========================
def kb_main() -> dict:
    return {
        "keyboard": [
            [{"text": "🎮 Игра"}, {"text": "⚙️ Настройки"}, {"text": "🎭 Роль/Класс"}],
            [{"text": "🧠 ИИ"}, {"text": "🎯 Тренировка"}, {"text": "🎬 VOD"}],
            [{"text": "🧟 Zombies"}, {"text": "📌 Профиль"}, {"text": "📊 Статус"}],
            [{"text": "💎 Premium"}, {"text": "🧹 Очистить память"}, {"text": "🧨 Сброс"}],
            [_miniapp_button()],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Опиши ситуацию/смерть одной строкой — разбор как от тиммейта…",
    }


# =========================
# PREMIUM HUB
# =========================
def kb_premium() -> dict:
    return {
        "keyboard": [
            [{"text": "🎙 Голос: Тиммейт/Коуч"}],
            [{"text": "😈 Режим мышления"}, {"text": "🧩 Настройки игры"}],
            [{"text": "🎯 Тренировка: План"}, {"text": "🎬 VOD: Разбор"}],
            [{"text": "🧠 Память: Статус"}],
            [_miniapp_button()],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Premium-панель…",
    }


# =========================
# VOICE MODE
# =========================
def kb_voice() -> dict:
    return {
        "keyboard": [
            [{"text": "🤝 Тиммейт"}, {"text": "📚 Коуч"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Выбери стиль общения…",
    }


# =========================
# SETTINGS ROOT
# =========================
def kb_settings() -> dict:
    return {
        "keyboard": [
            [{"text": "🎮 Выбрать игру"}],
            [{"text": "🖥 Платформа"}, {"text": "⌨️ Input"}],
            [{"text": "😈 Режим мышления"}],
            [{"text": "🧩 Настройки игры"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Выбери пункт настроек…",
    }


def kb_games() -> dict:
    return {
        "keyboard": [
            [{"text": "🔥 Warzone"}, {"text": "💣 BO7"}],
            [{"text": "🪖 BF6"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
    }


def kb_platform() -> dict:
    return {
        "keyboard": [
            [{"text": "🖥 PC"}, {"text": "🎮 PlayStation"}, {"text": "🎮 Xbox"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
    }


def kb_input() -> dict:
    return {
        "keyboard": [
            [{"text": "⌨️ KBM"}, {"text": "🎮 Controller"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
    }


def kb_difficulty() -> dict:
    return {
        "keyboard": [
            [{"text": "🧠 Normal"}, {"text": "🔥 Pro"}, {"text": "😈 Demon"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
    }


def kb_bf6_classes() -> dict:
    return {
        "keyboard": [
            [{"text": "🟥 Assault"}, {"text": "🟦 Recon"}],
            [{"text": "🟨 Engineer"}, {"text": "🟩 Medic"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
    }


def kb_roles() -> dict:
    return {
        "keyboard": [
            [{"text": "⚔️ Слэйер"}, {"text": "🚪 Энтри"}, {"text": "🧠 IGL"}],
            [{"text": "🛡 Саппорт"}, {"text": "🌀 Флекс"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
    }


def kb_game_settings_menu(game: str) -> dict:
    g = (game or "Warzone").strip()
    g_up = g.upper()

    if g_up == "BF6":
        return {
            "keyboard": [
                [{"text": "🪖 BF6: Class Settings"}],
                [{"text": "🎯 BF6: Aim/Sens"}],
                [{"text": "🎮 BF6: Controller Tuning"}, {"text": "⌨️ BF6: KBM Tuning"}],
                [{"text": "⬅️ Назад"}],
            ],
            "resize_keyboard": True,
            "is_persistent": True,
            "one_time_keyboard": False,
            "input_field_placeholder": "BF6 settings (EN)…",
        }

    if g_up == "BO7":
        return {
            "keyboard": [
                [{"text": "🎭 BO7: Роль"}],
                [{"text": "🎯 BO7: Aim/Sens"}],
                [{"text": "🎮 BO7: Controller"}, {"text": "⌨️ BO7: KBM"}],
                [{"text": "🧠 BO7: Мувмент/Позиционка"}, {"text": "🎧 BO7: Аудио/Видео"}],
                [{"text": "⬅️ Назад"}],
            ],
            "resize_keyboard": True,
            "is_persistent": True,
            "one_time_keyboard": False,
            "input_field_placeholder": "Настройки BO7…",
        }

    return {
        "keyboard": [
            [{"text": "🎭 Warzone: Роль"}],
            [{"text": "🎯 Warzone: Aim/Sens"}],
            [{"text": "🎮 Warzone: Controller"}, {"text": "⌨️ Warzone: KBM"}],
            [{"text": "🧠 Warzone: Мувмент/Позиционка"}, {"text": "🎧 Warzone: Аудио/Видео"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Настройки Warzone…",
    }


# =========================================================
# ZOMBIES (BACKWARD COMPAT)
# =========================================================
def kb_zombies_home() -> dict:
    return {
        "keyboard": [
            [{"text": "🗺 Карты"}, {"text": "🧪 Перки"}],
            [{"text": "🔫 Оружие"}, {"text": "🥚 Пасхалки"}],
            [{"text": "🧠 Стратегия раундов"}, {"text": "⚡ Быстрые советы"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Zombies: карта | раунд | от чего падаешь | что открыл…",
    }


def kb_zombies_maps() -> dict:
    return {
        "keyboard": [
            [{"text": "🧟 Ashes"}, {"text": "🧟 Astra"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Выбери карту…",
    }


def kb_zombies_sections() -> dict:
    return {
        "keyboard": [
            [{"text": "🚀 Старт/маршрут"}, {"text": "⚡ Pack-a-Punch"}, {"text": "🔫 Чудо-оружие"}],
            [{"text": "⚡ Перки (порядок)"}, {"text": "🔫 Оружие (2 слота)"}, {"text": "🧠 Ротации/позиции"}],
            [{"text": "👹 Спец-зомби/боссы"}, {"text": "🧩 Пасхалка (основная)"}, {"text": "🎁 Мини-пасхалки"}],
            [{"text": "💀 Ошибки/вайпы"}, {"text": "🧾 Чек-лист раунда"}, {"text": "🆘 Я застрял"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Напиши ключевое слово или выбери секцию…",
    }
