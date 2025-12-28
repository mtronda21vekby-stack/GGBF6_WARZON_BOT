# app/services/brain/memory.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class InMemoryStore:
    # ✅ принимает memory_max_turns (как у тебя в webhook.py)
    memory_max_turns: int = 20

    _turns: Dict[int, List[dict]] = field(default_factory=dict)
    _profiles: Dict[int, dict] = field(default_factory=dict)

    def add(self, chat_id: int, role: str, text: str) -> None:
        arr = self._turns.setdefault(chat_id, [])
        arr.append({"role": role, "content": text})
        if self.memory_max_turns and len(arr) > self.memory_max_turns:
            self._turns[chat_id] = arr[-self.memory_max_turns :]

    def get(self, chat_id: int) -> List[dict]:
        return list(self._turns.get(chat_id, []))

    def clear(self, chat_id: int) -> None:
        self._turns.pop(chat_id, None)

    def stats(self, chat_id: int) -> dict:
        turns = len(self._turns.get(chat_id, []))
        return {"turns": turns, "max_turns": int(self.memory_max_turns or 0)}

    # optional profile fallback storage
    def set_profile(self, chat_id: int, patch: dict) -> None:
        p = self._profiles.setdefault(chat_id, {})
        p.update(patch)

    def get_profile(self, chat_id: int) -> dict:
        return dict(self._profiles.get(chat_id, {}))
