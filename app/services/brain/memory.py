# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

@dataclass
class UserState:
    game: str = "warzone"
    style: str = "coach"
    turns: List[Tuple[str, str]] = field(default_factory=list)  # (user, bot)

class InMemoryStore:
    def __init__(self, memory_max_turns: int = 20):
        self.memory_max_turns = memory_max_turns
        self._users: Dict[int, UserState] = {}

    def get(self, user_id: int) -> UserState:
        if user_id not in self._users:
            self._users[user_id] = UserState()
        return self._users[user_id]

    def add_turn(self, user_id: int, user_text: str, bot_text: str) -> None:
        st = self.get(user_id)
        st.turns.append((user_text, bot_text))
        if len(st.turns) > self.memory_max_turns:
            st.turns = st.turns[-self.memory_max_turns :]

    def clear_memory(self, user_id: int) -> None:
        st = self.get(user_id)
        st.turns.clear()

    def reset(self, user_id: int) -> None:
        self._users[user_id] = UserState()
