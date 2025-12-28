from __future__ import annotations
from dataclasses import dataclass
from app.services.brain.memory import InMemoryStore


@dataclass
class Profile:
    user_id: int
    style: str = "coach"
    ai_enabled: bool = True


class ProfileService:
    def __init__(self, store: InMemoryStore):
        self.store = store
        self._profiles: dict[int, Profile] = {}

    def get(self, user_id: int) -> Profile:
        if user_id not in self._profiles:
            self._profiles[user_id] = Profile(user_id=user_id)
        return self._profiles[user_id]
