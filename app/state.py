# -*- coding: utf-8 -*-
import json
import os
import threading
import time
from datetime import datetime
from typing import Dict, Any, List

STATE_GUARD = threading.Lock()

USER_PROFILE: Dict[int, Dict[str, Any]] = {}
USER_MEMORY: Dict[int, List[Dict[str, str]]] = {}

def _today_key() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")

def ensure_profile(chat_id: int) -> Dict[str, Any]:
    return USER_PROFILE.setdefault(chat_id, {
        "game": "auto",          # auto|warzone|bf6|bo7
        "persona": "spicy",      # spicy|chill|pro
        "verbosity": "normal",   # short|normal|talkative
        "memory": "on",          # on|off
        "mode": "chat",          # chat|coach
        "player_level": "demon", # normal|pro|demon
        "day": _today_key(),
    })

def load_state(path: str, log) -> None:
    global USER_PROFILE, USER_MEMORY
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            USER_PROFILE = {int(k): v for k, v in (data.get("profiles") or {}).items()}
            USER_MEMORY  = {int(k): v for k, v in (data.get("memory") or {}).items()}
            log.info("State loaded: profiles=%d memory=%d", len(USER_PROFILE), len(USER_MEMORY))
    except Exception as e:
        log.warning("State load failed: %r", e)

def save_state(path: str, log) -> None:
    try:
        with STATE_GUARD:
            data = {
                "profiles": {str(k): v for k, v in USER_PROFILE.items()},
                "memory": {str(k): v for k, v in USER_MEMORY.items()},
                "saved_at": int(time.time()),
            }
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception as e:
        log.warning("State save failed: %r", e)

def update_memory(chat_id: int, role: str, content: str, max_turns: int = 10) -> None:
    p = ensure_profile(chat_id)
    if p.get("memory") != "on":
        return
    mem = USER_MEMORY.setdefault(chat_id, [])
    mem.append({"role": role, "content": content})
    max_len = max(4, max_turns * 2)
    if len(mem) > max_len:
        USER_MEMORY[chat_id] = mem[-max_len:]

def clear_memory(chat_id: int) -> None:
    USER_MEMORY.pop(chat_id, None)
