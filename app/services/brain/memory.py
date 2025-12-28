# -*- coding: utf-8 -*-
from __future__ import annotations
from collections import defaultdict


class PlayerMemory:
    def __init__(self, max_items: int = 10):
        self.max_items = max_items
        self._errors = defaultdict(list)

    def add_error(self, user_id: int, error: str):
        arr = self._errors[user_id]
        arr.append(error)
        if len(arr) > self.max_items:
            arr.pop(0)

    def common_error(self, user_id: int) -> str | None:
        arr = self._errors.get(user_id)
        if not arr:
            return None
        return max(set(arr), key=arr.count)
