# app/services/brain/memory.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import deque
from typing import Deque, Dict, List


class InMemoryStore:
    """
    Простая, стабильная память.
    Ничего не ломает.
    Готова к апгрейду до Ultra Brain.
    """

    def __init__(self, max_turns: int = 20):
        self.max_turns = max_turns
        self._data: Dict[int, Deque[dict]] = {}

    def add(self, chat_id: int, role: str, content: str):
        if chat_id not in self._data:
            self._data[chat_id] = deque(maxlen=self.max_turns)

        self._data[chat_id].append(
            {
                "role": role,
                "content": content,
            }
        )

    def get(self, chat_id: int) -> List[dict]:
        if chat_id not in self._data:
            return []
        return list(self._data[chat_id])

    def clear(self, chat_id: int):
        self._data.pop(chat_id, None)

    def stats(self, chat_id: int) -> dict:
        return {
            "turns": len(self._data.get(chat_id, [])),
            "limit": self.max_turns,
        }
