# -*- coding: utf-8 -*-
from __future__ import annotations


class PlayerRating:
    def __init__(self):
        self._score = {}

    def get(self, user_id: int) -> int:
        return self._score.get(user_id, 1000)

    def add(self, user_id: int, value: int):
        self._score[user_id] = self.get(user_id) + value

    def level(self, user_id: int) -> str:
        s = self.get(user_id)
        if s < 900:
            return "Bronze"
        if s < 1100:
            return "Silver"
        if s < 1300:
            return "Gold"
        if s < 1500:
            return "Platinum"
        return "Demon"
