# app/services/profiles/service.py
from __future__ import annotations

from dataclasses import dataclass

from app.services.brain.memory import InMemoryStore


DEFAULT_PROFILE = {
    "game": "AUTO",          # WARZONE / BF6 / BO7 / AUTO
    "input": "AUTO",         # KBM / CONTROLLER / AUTO
    "difficulty": "NORMAL",  # NORMAL / PRO / DEMON
    "ai": True,              # ON/OFF
}


@dataclass
class ProfileService:
    store: InMemoryStore

    def get(self, user_id: int) -> dict:
        p = DEFAULT_PROFILE | self.store.get_profile(user_id)
        return p

    def update(self, user_id: int, **patch) -> dict:
        p = self.get(user_id)
        p.update({k: v for k, v in patch.items() if v is not None})
        self.store.set_profile(user_id, p)
        return p
