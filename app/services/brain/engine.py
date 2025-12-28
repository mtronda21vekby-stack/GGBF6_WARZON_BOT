# -*- coding: utf-8 -*-
from __future__ import annotations

from app.services.brain.worlds import WarzoneWorld, BF6World, BO7World
from app.services.brain.memory import PlayerMemory
from app.services.brain.detector import detect_situation
from app.services.brain.dialogues import get_dialogue

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

        # --- AUTO DETECT ---
        situation = detect_situation(text)
        if situation:
            self.memory.add_error(user_id, situation)
            dialogue = get_dialogue(style, situation)
        else:
            dialogue = ""

        analysis = world.analyze(text, profile, style, self.memory)

        final = analysis
        if dialogue:
            final = f"{dialogue}\n\n{analysis}"

        return self._reply(final)

    def _reply(self, text: str):
        return type("R", (), {"text": text})
