# -*- coding: utf-8 -*-
from __future__ import annotations
from collections import defaultdict
from typing import Optional


class InMemoryStore:
    """
    Простая in-memory память.
    Не ломает архитектуру.
    Можно заменить на Redis / DB позже без изменений Brain.
    """

    def __init__(self):
        # user_id -> dict
        self._data = defaultdict(dict)

    # ---------- GENERIC ----------
    def get(self, user_id: int, key: str, default=None):
        return self._data[user_id].get(key, default)

    def set(self, user_id: int, key: str, value):
        self._data[user_id][key] = value

    def clear(self, user_id: int):
        self._data[user_id].clear()

    # ---------- AI MEMORY ----------
    def get_last_mistake(self, user_id: int) -> Optional[str]:
        return self._data[user_id].get("last_mistake")

    def set_last_mistake(self, user_id: int, text: str):
        self._data[user_id]["last_mistake"] = text

    def get_focus(self, user_id: int) -> Optional[str]:
        return self._data[user_id].get("focus")

    def set_focus(self, user_id: int, focus: str):
        self._data[user_id]["focus"] = focus
