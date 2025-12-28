# -*- coding: utf-8 -*-
from __future__ import annotations


class AIHook:
    """
    Заглушка под реальный ИИ (GPT / Claude / Local LLM)
    Архитектура готова — сейчас OFF
    """

    def __init__(self, enabled: bool = False):
        self.enabled = enabled

    async def analyze(self, context: dict) -> str | None:
        if not self.enabled:
            return None

        # Здесь в будущем будет реальный вызов ИИ
        # context = {
        #   game, mode, situation, memory, text
        # }

        return None
