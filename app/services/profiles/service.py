from dataclasses import dataclass
from app.domain.games import Game
from app.domain.devices import Device
from app.domain.difficulty import Difficulty


@dataclass
class Profile:
    user_id: int

    game: Game = Game.WARZONE
    device: Device | None = None
    difficulty: Difficulty = Difficulty.NORMAL

    ai_enabled: bool = True
    memory_enabled: bool = True


class ProfileService:
    def __init__(self):
        self._profiles: dict[int, Profile] = {}

    def get(self, user_id: int) -> Profile:
        if user_id not in self._profiles:
            self._profiles[user_id] = Profile(user_id=user_id)
        return self._profiles[user_id]
