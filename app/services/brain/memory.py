# app/services/brain/memory.py
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MemoryTurn:
    user_text: str
    bot_text: str


@dataclass
class InMemoryStore:
    memory_max_turns: int = 20
    _mem: dict[int, list[MemoryTurn]] = field(default_factory=dict)
    _profile: dict[int, dict] = field(default_factory=dict)

    # memory
    def add_turn(self, user_id: int, user_text: str, bot_text: str) -> None:
        turns = self._mem.setdefault(user_id, [])
        turns.append(MemoryTurn(user_text=user_text, bot_text=bot_text))
        if len(turns) > self.memory_max_turns:
            del turns[0 : len(turns) - self.memory_max_turns]

    def get_turns(self, user_id: int) -> list[MemoryTurn]:
        return list(self._mem.get(user_id, []))

    def clear(self, user_id: int) -> None:
        self._mem.pop(user_id, None)

    # profile
    def get_profile(self, user_id: int) -> dict:
        return dict(self._profile.get(user_id, {}))

    def set_profile(self, user_id: int, data: dict) -> None:
        self._profile[user_id] = dict(data)
