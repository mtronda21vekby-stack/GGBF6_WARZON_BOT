from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Profile:
    user_id: int

    ai_enabled: bool = True
    mem_enabled: bool = True
    quickbar_sent: bool = False

    game: str = "auto"       # auto / warzone / bf6 / bo7
    style: str = "spicy"
    answer: str = "normal"
    mode: str = "chat"       # chat / training / etc


class ProfileService:
    def __init__(self, store=None):
        self.store = store
        self._profiles: dict[int, Profile] = {}

    def get(self, user_id: int) -> Profile:
        if user_id not in self._profiles:
            self._profiles[user_id] = Profile(user_id=user_id)
        return self._profiles[user_id]
