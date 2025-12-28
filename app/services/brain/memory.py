from __future__ import annotations
from collections import defaultdict, deque


class InMemoryStore:
    def __init__(self, memory_max_turns: int = 12):
        self.memory_max_turns = memory_max_turns
        self._mem = defaultdict(lambda: deque(maxlen=memory_max_turns))

    def add(self, user_id: int, role: str, text: str) -> None:
        self._mem[user_id].append({"role": role, "text": text})

    def get(self, user_id: int):
        return list(self._mem[user_id])

    def clear(self, user_id: int) -> None:
        self._mem[user_id].clear()
