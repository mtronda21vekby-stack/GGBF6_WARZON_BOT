from __future__ import annotations

from dataclasses import dataclass
from app.services.brain.memory import InMemoryStore
from app.services.profiles.service import ProfileService
from app.services.brain.llm import LLMClient


@dataclass
class BrainReply:
    text: str


class BrainEngine:
    def __init__(self, store: InMemoryStore, profiles: ProfileService, settings):
        self.store = store
        self.profiles = profiles
        self.settings = settings

        self.llm: LLMClient | None = None
        if settings.AI_ENABLED and settings.AI_API_KEY:
            self.llm = LLMClient(
                api_key=settings.AI_API_KEY,
                base_url=settings.AI_BASE_URL,
                model=settings.AI_MODEL,
                timeout_sec=settings.AI_TIMEOUT_SEC,
            )

    async def handle_text(self, user_id: int, text: str) -> BrainReply:
        profile = self.profiles.get(user_id)

        # memory add user
        self.store.add(user_id, "user", text)

        # If AI is enabled and configured
        if self.llm is not None and profile.ai_enabled:
            system = (
                "Ты — FPS Coach для Warzone/BF6. "
                "Отвечай коротко и по делу: 1) диагноз 2) 3 шага тренировки 3) одна настройка/совет. "
                "Если мало данных — задай 1 уточняющий вопрос."
            )

            turns = self.store.get(user_id)
            history = []
            for t in turns[-10:]:
                role = "assistant" if t.role == "assistant" else "user"
                history.append({"role": role, "content": t.text})

            messages = [{"role": "system", "content": system}] + history

            try:
                out = await self.llm.chat(messages)
                self.store.add(user_id, "assistant", out)
                return BrainReply(text=out)
            except Exception:
                # AI failed → fallback without crashing
                pass

        # Fallback (no AI or AI failed)
        fallback = (
            "Я на связи. Напиши: какая игра (Warzone/BF6), твой input (мышь/геймпад) "
            "и что болит (аим, мувмент, позиционка). Я соберу план."
        )
        self.store.add(user_id, "assistant", fallback)
        return BrainReply(text=fallback)

    def clear_memory(self, user_id: int) -> None:
        self.store.clear(user_id)

    def toggle_ai(self, user_id: int) -> bool:
        p = self.profiles.get(user_id)
        p.ai_enabled = not p.ai_enabled
        return p.ai_enabled
