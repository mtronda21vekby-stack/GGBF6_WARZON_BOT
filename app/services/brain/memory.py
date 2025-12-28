# app/services/brain/memory.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, TypedDict


Role = Literal["user", "assistant", "system"]


class Turn(TypedDict):
    role: Role
    content: str


@dataclass
class InMemoryStore:
    # принимаем разные имена параметров, чтобы НЕ падать на несовпадении
    memory_max_turns: int = 20
    max_turns: int | None = None
    _mem: Dict[int, List[Turn]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.max_turns is not None:
            self.memory_max_turns = int(self.max_turns)

    def add(self, chat_id: int, role: Role, content: str) -> None:
        arr = self._mem.setdefault(int(chat_id), [])
        arr.append({"role": role, "content": str(content)})
        # режем только хвост памяти, функционал НЕ режем
        limit = max(4, int(self.memory_max_turns) * 2)  # user+assistant
        if len(arr) > limit:
            self._mem[int(chat_id)] = arr[-limit:]

    def get(self, chat_id: int) -> List[Turn]:
        return list(self._mem.get(int(chat_id), []))

    def clear(self, chat_id: int) -> None:
        self._mem.pop(int(chat_id), None)

    def stats(self, chat_id: int) -> dict:
        arr = self._mem.get(int(chat_id), [])
        return {"turns": len(arr), "max_turns": self.memory_max_turns}
