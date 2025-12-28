# app/services/brain/memory.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass
class InMemoryStore:
    """
    Простейшая память: хранит последние N сообщений на чат.
    Совместима с твоими вызовами:
      - InMemoryStore(memory_max_turns=...)
      - store.add/get/clear/stats
      - store.set_profile(...) (на случай фолбэка)
    """
    memory_max_turns: int = 20
    _data: Dict[int, List[dict]] = field(default_factory=dict)
    _profiles: Dict[int, dict] = field(default_factory=dict)

    def __init__(self, memory_max_turns: int = 20, max_turns: int | None = None):
        if max_turns is not None:
            memory_max_turns = max_turns
        self.memory_max_turns = int(memory_max_turns or 20)
        self._data = {}
        self._profiles = {}

    def add(self, chat_id: int, role: str, content: str) -> None:
        arr = self._data.setdefault(int(chat_id), [])
        arr.append({"role": role, "content": content})
        # держим только последние 2*turns (user+assistant)
        limit = max(2, self.memory_max_turns * 2)
        if len(arr) > limit:
            self._data[int(chat_id)] = arr[-limit:]

    def get(self, chat_id: int) -> List[dict]:
        return list(self._data.get(int(chat_id), []))

    def clear(self, chat_id: int) -> None:
        self._data.pop(int(chat_id), None)

    def stats(self, chat_id: int) -> dict:
        arr = self._data.get(int(chat_id), [])
        return {"turns": len(arr), "max_turns": self.memory_max_turns}

    # optional fallback profile storage
    def set_profile(self, chat_id: int, patch: dict) -> None:
        base = self._profiles.get(int(chat_id), {})
        base.update(patch or {})
        self._profiles[int(chat_id)] = base

    def get_profile(self, chat_id: int) -> dict:
        return dict(self._profiles.get(int(chat_id), {}))
