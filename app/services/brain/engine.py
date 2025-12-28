from __future__ import annotations

from dataclasses import dataclass

from app.services.ai.openai_client import OpenAIClient
from app.services.brain.coach import build_plan


@dataclass
class BrainReply:
    text: str


class BrainEngine:
    def __init__(self, store, profiles, settings):
        self.store = store
        self.profiles = profiles
        self.settings = settings
        self.ai = OpenAIClient()

    async def handle_text(self, user_id: int, text: str) -> BrainReply:
        p = self.profiles.get(user_id) if self.profiles else None
        game = (getattr(p, "game", None) or "warzone")
        device = (getattr(p, "device", None) or "auto")
        diff = (getattr(p, "difficulty", None) or "normal")

        # Если AI включён в профиле и есть ключ — используем OpenAI
        ai_enabled = bool(getattr(p, "ai_enabled", True)) if p else True
        if ai_enabled and self.ai.enabled():
            system = (
                "Ты элитный FPS Coach. Цель: довести игрока до топ-уровня.\n"
                "Отвечай структурно:\n"
                "1) Диагноз (1–2 предложения)\n"
                "2) Почему (коротко)\n"
                "3) Правило (1 строка)\n"
                "4) Упражнения (3–6 пунктов)\n"
                "5) План на 7 дней (коротко)\n"
                "Пиши по-русски. Без воды."
            )

            user = (
                f"Профиль:\n"
                f"- game: {game}\n"
                f"- input: {device}\n"
                f"- difficulty: {diff}\n\n"
                f"Сообщение игрока:\n{text}\n\n"
                f"Дай разбор и план."
            )

            res = await self.ai.generate(system=system, user=user)
            if res.ok and res.text.strip():
                return BrainReply(text=res.text.strip())

            # если AI упал — фолбэк
            fallback = build_plan(game=game, device=device, diff=diff, msg=text).text
            return BrainReply(text=fallback + f"\n\n⚠️ AI error: {res.error}")

        # Фолбэк без ключа/AI OFF
        out = build_plan(game=game, device=device, diff=diff, msg=text)
        return BrainReply(text=out.text)
