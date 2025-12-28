from __future__ import annotations
from dataclasses import dataclass

from app.domain.enums import Game, Mode, InputDevice, SkillTier
from app.services.brain.memory import InMemoryStore


@dataclass
class Profile:
    user_id: int
    ai_enabled: bool = True

    game: Game = Game.WARZONE
    mode: Mode = Mode.WZ_BR
    device: InputDevice = InputDevice.PS
    tier: SkillTier = SkillTier.NORMAL


class ProfileService:
    def __init__(self, store: InMemoryStore):
        self.store = store
        self._profiles: dict[int, Profile] = {}

    def get(self, user_id: int) -> Profile:
        if user_id not in self._profiles:
            self._profiles[user_id] = Profile(user_id=user_id)
        return self._profiles[user_id]
