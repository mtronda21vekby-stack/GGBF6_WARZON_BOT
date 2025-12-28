# app/services/brain/memory.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class InMemoryStore:
    """
    Простая память по chat_id.
    ВАЖНО: принимает разные имена аргументов, чтобы не ломаться:
      - memory_max_turns
      - max_turns
      - turns
    """
    max_turns: int = 20
    _mem: Dict[int, List[dict]] = field(default_factory=dict)
    _profile: Dict[int, Dict[str, Any]] = field(default_factory=dict)

    def __init__(self, memory_max_turns: int = 20, max_turns: int | None = None, turns: int | None = None):
        if max_turns is not None:
            self.max_turns = int(max_turns)
        elif turns is not None:
            self.max_turns = int(turns)
        else:
            self.max_turns = int(memory_max_turns)

        self._mem = {}
        self._profile = {}

    def add(self, chat_id: int, role: str, text: str) -> None:
        arr = self._mem.setdefault(chat_id, [])
        arr.append({"role": role, "content": text})
        if len(arr) > self.max_turns:
            self._mem[chat_id] = arr[-self.max_turns :]

    def get(self, chat_id: int) -> List[dict]:
        return list(self._mem.get(chat_id, []))

    def clear(self, chat_id: int) -> None:
        self._mem.pop(chat_id, None)

    def stats(self, chat_id: int) -> dict:
        return {"turns": len(self._mem.get(chat_id, [])), "max_turns": self.max_turns}

    # профиль (fallback)
    def set_profile(self, chat_id: int, patch: Dict[str, Any]) -> None:
        cur = self._profile.setdefault(chat_id, {})
        cur.update(patch)

    def get_profile(self, chat_id: int) -> Dict[str, Any]:
        return dict(self._profile.get(chat_id, {}))
