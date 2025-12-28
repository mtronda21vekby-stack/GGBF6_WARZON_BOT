# -*- coding: utf-8 -*-
from __future__ import annotations

from app.services.brain.worlds import WarzoneWorld, BF6World, BO7World
from app.services.brain.memory import PlayerMemory
from app.services.brain.detector import detect_situation
from app.services.brain.dialogues import get_dialogue
from app.services.brain.premium import get_premium_tip
from app.services.brain.ai_hook import AIHook


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
        self.ai = AIHook(enabled=False)  # ИИ ВЫКЛЮЧЕН, ГОТОВ НА БУДУЩЕЕ

    async def handle_text(self, user_id: int, text: str):
        profile = self.profiles.get(user_id)

        game = profile.game or "warzone"
        style = profile.mode or "normal"

        world = WORLD_MAP.get(game)
        if not world:
            return self._reply("Мир не найден.")

        # ---------- AUTO DETECT ----------
        situation = detect_situation(text)
        dialogue = ""

        if situation:
            self.memory.add_error(user_id, situation)
            dialogue = get_dialogue(style, situation)

        # ---------- WORLD ANALYSIS ----------
        analysis = world.analyze(text, profile, style, self.memory)

        # ---------- PREMIUM (OFF BY DEFAULT) ----------
        premium = ""
        if getattr(profile, "premium", False):
            premium = get_premium_tip(game)

        # ---------- AI HOOK ----------
        ai_text = await self.ai.analyze({
            "game": game,
            "style": style,
            "situation": situation,
            "memory": self.memory,
            "text": text,
        })

        parts = []
        if dialogue:
            parts.append(dialogue)
        parts.append(analysis)
        if premium:
            parts.append(premium)
        if ai_text:
            parts.append(ai_text)

        return self._reply("\n\n".join(parts))

    def _reply(self, text: str):
        return type("R", (), {"text": text})
