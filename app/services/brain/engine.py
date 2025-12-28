# -*- coding: utf-8 -*-
from __future__ import annotations

class BrainEngine:
    def __init__(self, store, profiles, settings):
        self.store = store
        self.profiles = profiles
        self.settings = settings

    async def handle_text(self, user_id: int, text: str):
        profile = self.profiles.get(user_id)

        game = getattr(profile, "game", "warzone")
        mode = getattr(profile, "mode", "normal")
        role = getattr(profile, "role", None)

        reply = self._analyze(text, game, mode, role)
        return type("Reply", (), {"text": reply})

    def _analyze(self, text: str, game: str, mode: str, role: str | None) -> str:
        base = [
            f"🎮 Игра: {game.upper()}",
            f"🎭 Роль: {role.upper() if role else 'НЕ ВЫБРАНА'}",
            f"😈 Режим: {mode.upper()}",
            "",
        ]

        # Core logic (offline, premium-style)
        if mode == "demon":
            base += [
                "❌ Ты умер не из-за аима.",
                "Причина: плохой тайминг или позиция.",
                "Правило топов: никогда не пикай без плана отхода.",
                "Сейчас: смени угол и темп.",
                "10 минут тренировки: контроль выхода + флик."
            ]
        elif mode == "pro":
            base += [
                "Ошибка: переоценка позиции.",
                "Что делают топы: играют от таймингов.",
                "Следующий шаг: заранее планируй выход.",
                "Мини-тренировка: 5–10 минут контроля углов."
            ]
        else:
            base += [
                "Ты попал в невыгодную ситуацию.",
                "Попробуй играть спокойнее.",
                "Сфокусируйся на выживании."
            ]

        return "\n".join(base)
