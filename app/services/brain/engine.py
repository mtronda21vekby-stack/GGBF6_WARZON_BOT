# -*- coding: utf-8 -*-
from __future__ import annotations

from app.services.brain.worlds import WarzoneWorld, BF6World, BO7World
from app.services.brain.memory import PlayerMemory

WORLD_MAP = {
    "warzone": WarzoneWorld(),
    "bf6": BF6World(),
    "bo7": BO7World(),
}


class BrainEngine:
    def __init__(self, store, profiles, settings):
        self.store = store
        self.profiles = profiles
        self.settings = settings
        self.memory = PlayerMemory()

    async def handle_text(self, user_id: int, text: str):
        profile = self.profiles.get(user_id)
        game = profile.game or "warzone"
        style = profile.mode or "normal"

        world = WORLD_MAP.get(game)
        if not world:
            return self._reply("Мир не найден.")

        # простая фиксация ошибки
        if "умер" in text.lower() or "проиграл" in text.lower():
            self.memory.add_error(user_id, "Плохая позиция")

        answer = world.analyze(text, profile, style, self.memory)
        return self._reply(answer)

    def _reply(self, text: str):
        return type("R", (), {"text": text})
