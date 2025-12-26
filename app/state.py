import json
import os
import threading
import time
from datetime import datetime
from typing import Dict, Any, List
import random

STATE_GUARD = threading.Lock()
LOCKS_GUARD = threading.Lock()

USER_PROFILE: Dict[int, Dict[str, Any]] = {}
USER_MEMORY: Dict[int, List[Dict[str, str]]] = {}
USER_STATS: Dict[int, Dict[str, int]] = {}
USER_DAILY: Dict[int, Dict[str, Any]] = {}
LAST_MSG_TS: Dict[int, float] = {}
CHAT_LOCKS: Dict[int, threading.Lock] = {}

DAILY_POOL = [
    ("angles", "5 файтов подряд — не репикай тот же угол. После первого хита меняй позицию."),
    ("info", "3 файта подряд — сначала инфо (звук/радар), потом выход. Без ‘на авось’."),
    ("center", "10 минут — держи прицел на уровне головы/плеч. Без ‘в пол’."),
    ("reset", "Каждый файт — после контакта 1 раз: ‘плейты/перезар/ресет’ перед репиком."),
]

def _today_key() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")

def get_lock(chat_id: int) -> threading.Lock:
    with LOCKS_GUARD:
        if chat_id not in CHAT_LOCKS:
            CHAT_LOCKS[chat_id] = threading.Lock()
        return CHAT_LOCKS[chat_id]

def ensure_profile(chat_id: int) -> Dict[str, Any]:
    # ⚠️ Важно: ничего не удаляем, только добавляем новые поля для будущего.
    return USER_PROFILE.setdefault(chat_id, {
        "game": "auto",
        "persona": "spicy",
        "verbosity": "normal",
        "memory": "on",
        "ui": "show",
        "mode": "chat",
        "speed": "normal",        # normal | lightning
        "last_question": "",
        "last_answer": "",
        "page": "main",           # main | zombies | wz | bf6 | bo7
        "zmb_map": "ashes",

        # ===== NEW: per-game device & tier presets (future-proof) =====
        "wz_device": "pad",       # pad | mnk
        "bo7_device": "pad",
        "bf6_device": "pad",

        "wz_tier": "normal",      # normal | demon | pro
        "bo7_tier": "normal",
        "bf6_tier": "normal",

        # ===== NEW: player level / style knobs =====
        "player_level": "normal", # normal | demon | pro (общий уровень игрока)
    })

def load_state(state_path: str, log) -> None:
    global USER_PROFILE, USER_MEMORY, USER_STATS, USER_DAILY
    try:
        if os.path.exists(state_path):
            with open(state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            USER_PROFILE = {int(k): v for k, v in (data.get("profiles") or {}).items()}
            USER_MEMORY = {int(k): v for k, v in (data.get("memory") or {}).items()}
            USER_STATS = {int(k): v for k, v in (data.get("stats") or {}).items()}
            USER_DAILY = {int(k): v for k, v in (data.get("daily") or {}).items()}
            log.info("State loaded: profiles=%d memory=%d stats=%d daily=%d",
                     len(USER_PROFILE), len(USER_MEMORY), len(USER_STATS), len(USER_DAILY))
    except Exception as e:
        log.warning("State load failed: %r (starting clean)", e)

def save_state(state_path: str, log) -> None:
    try:
        with STATE_GUARD:
            data = {
                "profiles": {str(k): v for k, v in USER_PROFILE.items()},
                "memory": {str(k): v for k, v in USER_MEMORY.items()},
                "stats": {str(k): v for k, v in USER_STATS.items()},
                "daily": {str(k): v for k, v in USER_DAILY.items()},
                "saved_at": int(time.time()),
            }
        tmp = state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, state_path)
    except Exception as e:
        log.warning("State save failed: %r", e)

def autosave_loop(stop: threading.Event, state_path: str, log, interval_s: int = 60) -> None:
    while not stop.is_set():
        stop.wait(interval_s)
        if stop.is_set():
            break
        save_state(state_path, log)

def throttle(chat_id: int, min_seconds_between_msg: float) -> bool:
    now = time.time()
    last = LAST_MSG_TS.get(chat_id, 0.0)
    if now - last < min_seconds_between_msg:
        return True
    LAST_MSG_TS[chat_id] = now
    return False

def update_memory(chat_id: int, role: str, content: str, memory_max_turns: int) -> None:
    p = ensure_profile(chat_id)
    if p.get("memory", "on") != "on":
        return
    mem = USER_MEMORY.setdefault(chat_id, [])
    mem.append({"role": role, "content": content})
    max_len = max(2, memory_max_turns * 2)
    if len(mem) > max_len:
        USER_MEMORY[chat_id] = mem[-max_len:]

def clear_memory(chat_id: int) -> None:
    USER_MEMORY.pop(chat_id, None)
    p = ensure_profile(chat_id)
    p["last_answer"] = ""
    p["last_question"] = ""

def ensure_daily(chat_id: int) -> Dict[str, Any]:
    d = USER_DAILY.setdefault(chat_id, {})
    if d.get("day") != _today_key() or not d.get("id"):
        cid, text = random.choice(DAILY_POOL)
        USER_DAILY[chat_id] = {"day": _today_key(), "id": cid, "text": text, "done": 0, "fail": 0}
    return USER_DAILY[chat_id]