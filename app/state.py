import json
import os
import time
from typing import Dict, Any, List


class StateStore:
    """
    Простая память:
    - режим пользователя
    - история последних сообщений (контекст)
    Хранение: data/state.json
    """

    def __init__(self, path: str, history_limit: int = 12):
        self.path = path
        self.history_limit = history_limit
        self.db: Dict[str, Any] = {"users": {}}
        self._load()

    def _load(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            self._save()
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self.db = json.load(f)
            if "users" not in self.db:
                self.db = {"users": {}}
        except Exception:
            self.db = {"users": {}}
            self._save()

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.db, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def get_mode(self, user_id: int) -> str:
        u = self.db["users"].get(str(user_id), {})
        return u.get("mode", "chat")

    def set_mode(self, user_id: int, mode: str):
        u = self.db["users"].setdefault(str(user_id), {})
        u["mode"] = mode
        u["updated_at"] = time.time()
        self._save()

    def get_history(self, user_id: int) -> List[Dict[str, str]]:
        u = self.db["users"].get(str(user_id), {})
        h = u.get("history", [])
        if not isinstance(h, list):
            return []
        return h[-self.history_limit:]

    def push(self, user_id: int, role: str, content: str):
        u = self.db["users"].setdefault(str(user_id), {})
        h = u.setdefault("history", [])
        if not isinstance(h, list):
            h = []
            u["history"] = h
        h.append({"role": role, "content": content})
        u["updated_at"] = time.time()
        if len(h) > self.history_limit * 3:
            u["history"] = h[-self.history_limit * 2 :]
        self._save()

    def clear(self, user_id: int):
        u = self.db["users"].setdefault(str(user_id), {})
        u["history"] = []
        u["updated_at"] = time.time()
        self._save()