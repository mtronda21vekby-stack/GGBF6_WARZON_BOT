# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from app.services.llm.client import LLMClient
from app.services.brain.prompts import build_ai_messages


class AIHook:
    """
    AI Hook: если включён и есть ключ — добавляет “реальный ИИ” к ответу.
    Ничего не ломает: если выключен/нет ключа -> возвращает None.
    """

    def __init__(self):
        # включение флагом (можно держать OFF пока не готов)
        self.enabled_flag = os.getenv("AI_ENABLED", "0").strip() == "1"
        self.client = LLMClient()

    def enabled(self) -> bool:
        return self.enabled_flag and self.client.enabled()

    async def analyze(
        self,
        *,
        game: str,
        mode: str,
        role: str | None,
        platform: str | None,
        input_: str | None,
        world_settings: dict | None,
        user_text: str,
        memory_hint: str | None = None,
    ) -> str | None:
        if not self.enabled():
            return None

        messages = build_ai_messages(
            game=game,
            mode=mode,
            role=role,
            platform=platform,
            input_=input_,
            world_settings=world_settings,
            user_text=user_text,
            memory_hint=memory_hint,
        )

        out = await self.client.chat(messages, temperature=0.35, max_tokens=650)
        return out or None
