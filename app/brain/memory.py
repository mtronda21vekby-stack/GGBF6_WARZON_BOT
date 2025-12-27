import json
import os
from dataclasses import dataclass

@dataclass
class UserState:
    style: str = "default"
    last_topic: str = ""
    turns: int = 0

class MemoryStore:
    """
    Лёгкая память “на будущее”.
    На free Render диск не гарантирован навсегда — но как скелет норм.
    Потом заменим на Redis/DB.
    """
    def __init__(self, path: str = "/tmp/ggbf6_memory.json"):
        self.path = path
        self.data = {}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {}

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get(self, user_id: int) -> UserState:
        raw = self.data.get(str(user_id), {})
        return UserState(**raw) if isinstance(raw, dict) else UserState()

    def set(self, user_id: int, st: UserState):
        self.data[str(user_id)] = {
            "style": st.style,
            "last_topic": st.last_topic,
            "turns": st.turns,
        }
        self._save()

    def clear(self, user_id: int):
        self.data.pop(str(user_id), None)
        self._save()
