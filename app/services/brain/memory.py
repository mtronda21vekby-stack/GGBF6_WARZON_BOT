from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class Turn:
    role: str   # "user" / "assistant"
    text: str


class InMemoryStore:
    def __init__(self, memory_max_turns: int = 20):
        self.memory_max_turns = memory_max_turns
        self._mem: Dict[int, List[Turn]] = {}

    def add(self, user_id: int, role: str, text: str) -> None:
        turns = self._mem.setdefault(user_id, [])
        turns.append(Turn(role=role, text=text))
        # keep last N turns
        if len(turns) > self.memory_max_turns:
            self._mem[user_id] = turns[-self.memory_max_turns :]

    def get(self, user_id: int) -> list[Turn]:
        return list(self._mem.get(user_id, []))

    def clear(self, user_id: int) -> None:
        self._mem[user_id] = []
