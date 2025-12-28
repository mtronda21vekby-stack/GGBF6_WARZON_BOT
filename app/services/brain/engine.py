# -*- coding: utf-8 -*-
from __future__ import annotations

from app.services.brain.worlds import WarzoneWorld, BF6World, BO7World
from app.services.brain.memory import PlayerMemory
from app.services.brain.detector import detect_situation
from app.services.brain.dialogues import get_dialogue
from app.services.brain.decision import detect_bad_decision, build_decision_feedback
from app.services.brain.loadouts import ROLE_LOADOUTS
from app.services.brain.rating import PlayerRating
from app.services.brain.premium import get_premium_tip
from app.services.brain.ai_hook import AIHook
from app.services.brain.season import SeasonManager


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
        self.rating = PlayerRating()
        self.season = SeasonManager(season_id="S1")
        self.ai = AIHook(enabled=False)

    async def handle_text(self, user_id: int, text: str):
        profile = self.profiles.get(user_id)

        game = (profile.game or "warzone").lower()
        style = (profile.mode or "normal").lower()
        role = getattr(profile, "role", None)

        world = WORLD_MAP.get(game)
        if not world:
            return self._reply("Мир не найден.")

        parts = []

        # --- AUTO DETECT (ситуация) ---
        situation = detect_situation(text)
        if situation:
            self.memory.add_error(user_id, situation)
            d = get_dialogue(style, situation)
            if d:
                parts.append(d)
            self.rating.add(user_id, -15)

        # --- BAD DECISION ---
        bad = detect_bad_decision(game, text)
        if bad:
            self.memory.add_error(user_id, bad)
            parts.append(build_decision_feedback(game, bad))
            self.rating.add(user_id, -25)
        else:
            self.rating.add(user_id, +5)

        # --- ROLE / LOADOUT ---
        if role:
            info = ROLE_LOADOUTS.get(game, {}).get(role)
            if info:
                parts.append(
                    f"🎭 РОЛЬ: {info['role']}\n"
                    f"🔫 ОРУЖИЕ: {', '.join(info['weapons'])}\n"
                    f"🎯 ФОКУС: {info['focus']}"
                )

        # --- WORLD ANALYSIS ---
        parts.append(world.analyze(text, profile, style, self.memory))

        # --- RATING / SEASON ---
        lvl = self.rating.level(user_id)
        score = self.rating.get(user_id)
        parts.append(f"📊 РЕЙТИНГ: {lvl} ({score}) | 🗓 {self.season.season_id}")

        # --- PREMIUM ---
        if getattr(profile, "premium", False):
            parts.append(get_premium_tip(game))

        # --- AI HOOK ---
        ai_text = await self.ai.analyze({
            "game": game,
            "style": style,
            "text": text,
            "memory": self.memory,
        })
        if ai_text:
            parts.append(ai_text)

        return self._reply("\n\n".join([p for p in parts if p]))

    def _reply(self, text: str):
        return type("R", (), {"text": text})
