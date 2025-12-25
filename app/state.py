# app/state.py
# -*- coding: utf-8 -*-

import json
import os
import threading
import time
from datetime import datetime
from typing import Dict, Any, List

from app import config
from app.log import log

USER_PROFILE: Dict[int, Dict[str, Any]] = {}
USER_MEMORY: Dict[int, List[Dict[str, str]]] = {}
USER_STATS: Dict[int, Dict[str, int]] = {}
USER_DAILY: Dict[int, Dict[str, Any]] = {}
LAST_MSG_TS: Dict[int, float] = {}

STATE_GUARD = threading.Lock()


def ensure_profile(chat_id: int) -> Dict[str, Any]:
    """
    Важно: тут должны быть ВСЕ дефолтные поля, которые читают ui/handlers/ai.
    """
    return USER_PROFILE.setdefault(chat_id, {
        "game": "auto",
        "persona": "spicy",
        "verbosity": "normal",
        "memory": "on",
        "ui": "show",
        "mode": "chat",
        "ai": "on",            # 🤖 on/off (чтобы кнопка работала)
        "page": "main",        # main | zombies | more
        "zmb_map": "ashes",
        "lightning": "off",    # ⚡ off/on
        "last_answer": "",
        "last_question": "",
    })


def load_state() -> None:
    global USER_PROFILE, USER_MEMORY, USER_STATS, USER_DAILY
    try:
        if os.path.exists(config.STATE_PATH):
            with open(config.STATE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            USER_PROFILE = {int(k): v for k, v in (data.get("profiles") or {}).items()}
            USER_MEMORY = {int(k): v for k, v in (data.get("memory") or {}).items()}
            USER_STATS = {int(k): v for k, v in (data.get("stats") or {}).items()}
            USER_DAILY = {int(k): v for k, v in (data.get("daily") or {}).items()}

            # ✅ миграция: если старые профили без "ai" — добавим
            for cid, p in USER_PROFILE.items():
                if "ai" not in p:
                    p["ai"] = "on"

            log.info(
                "State loaded: profiles=%d memory=%d stats=%d daily=%d",
                len(USER_PROFILE), len(USER_MEMORY), len(USER_STATS), len(USER_DAILY)
            )
    except Exception as e:
        log.warning("State load failed: %r (starting clean)", e)


def save_state() -> None:
    try:
        with STATE_GUARD:
            data = {
                "profiles": {str(k): v for k, v in USER_PROFILE.items()},
                "memory": {str(k): v for k, v in USER_MEMORY.items()},
                "stats": {str(k): v for k, v in USER_STATS.items()},
                "daily": {str(k): v for k, v in USER_DAILY.items()},
                "saved_at": int(time.time()),
            }

        tmp = config.STATE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, config.STATE_PATH)
    except Exception as e:
        log.warning("State save failed: %r", e)


def autosave_loop(stop: threading.Event, interval_s: int = 60) -> None:
    while not stop.is_set():
        stop.wait(interval_s)
        if stop.is_set():
            break
        save_state()


def throttle(chat_id: int) -> bool:
    now = time.time()
    last = LAST_MSG_TS.get(chat_id, 0.0)
    if now - last < config.MIN_SECONDS_BETWEEN_MSG:
        return True
    LAST_MSG_TS[chat_id] = now
    return False


def update_memory(chat_id: int, role: str, content: str) -> None:
    p = ensure_profile(chat_id)
    if p.get("memory", "on") != "on":
        return

    mem = USER_MEMORY.setdefault(chat_id, [])
    mem.append({"role": role, "content": content})

    max_len = max(2, config.MEMORY_MAX_TURNS * 2)
    if len(mem) > max_len:
        USER_MEMORY[chat_id] = mem[-max_len:]


def clear_memory(chat_id: int) -> None:
    USER_MEMORY.pop(chat_id, None)
    p = ensure_profile(chat_id)
    p["last_answer"] = ""
    p["last_question"] = ""


def reset_all(chat_id: int) -> None:
    """
    Полный сброс профиля/памяти/стат/дейли.
    Используется в handlers.py (action:reset_all).
    """
    USER_PROFILE.pop(chat_id, None)
    USER_MEMORY.pop(chat_id, None)
    USER_STATS.pop(chat_id, None)
    USER_DAILY.pop(chat_id, None)
    LAST_MSG_TS.pop(chat_id, None)


# ===== Daily challenge =====
DAILY_POOL = [
    ("angles", "5 файтов подряд — не репикай тот же угол. После первого хита меняй позицию."),
    ("info", "3 файта подряд — сначала инфо (звук/радар), потом выход. Без ‘на авось’."),
    ("center", "10 минут — держи прицел на уровне головы/плеч. Без ‘в пол’."),
    ("reset", "Каждый файт — после контакта 1 раз: ‘плейты/перезар/ресет’ перед репиком."),
]


def _today_key() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def ensure_daily(chat_id: int) -> Dict[str, Any]:
    d = USER_DAILY.setdefault(chat_id, {})
    if d.get("day") != _today_key() or not d.get("id"):
        import random
        cid, text = random.choice(DAILY_POOL)
        USER_DAILY[chat_id] = {"day": _today_key(), "id": cid, "text": text, "done": 0, "fail": 0}
    return USER_DAILY[chat_id]
