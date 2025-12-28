from __future__ import annotations
from dataclasses import dataclass
from typing import Any

# доменные enum'ы (если их ещё нет — добавим позже, сейчас не мешают)
try:
    from app.domain.games import Game
    from app.domain.devices import Device
    from app.domain.difficulty import Difficulty
except Exception:
    Game = None
    Device = None
    Difficulty = None


@dataclass
class Profile:
    user_id: int

    # базовые настройки
    game: str = "warzone"          # warzone / bf6 / bo7
    device: str | None = None      # kbm / pad
    difficulty: str = "normal"     # normal / pro / demon

    # флаги
    ai_enabled: bool = True
    memory_enabled: bool = True

    # UI
    quickbar_sent: bool = False


class ProfileService:
    def __init__(self, store: Any | None = None):
        # store оставляем, даже если пока не используем
        self.store = store
        self._profiles: dict[int, Profile] = {}

    def get(self, user_id: int) -> Profile:
        if user_id not in self._profiles:
            self._profiles[user_id] = Profile(user_id=user_id)
        return self._profiles[user_id]

    def clear(self, user_id: int):
        if user_id in self._profiles:
            del self._profiles[user_id]
