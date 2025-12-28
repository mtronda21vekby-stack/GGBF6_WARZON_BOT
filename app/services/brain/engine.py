# -*- coding: utf-8 -*-
from __future__ import annotations

from app.services.brain.worlds import WarzoneWorld, BF6World, BO7World


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

    async def handle_text(self, user_id: int, text: str):
        profile = self.profiles.get(user_id)
        game = profile.game or "warzone"

        world = WORLD_MAP.get(game)

        if not world:
            return self._reply("Мир не найден.")

        # --- INTRO ---
        if text.lower() in ("анализ", "ai", "🧠 ии"):
            return self._reply(world.intro())

        # --- WORLD ANALYSIS ---
        answer = world.analyze(text, profile)
        return self._reply(answer)

    def _reply(self, text: str):
        return type("R", (), {"text": text})
