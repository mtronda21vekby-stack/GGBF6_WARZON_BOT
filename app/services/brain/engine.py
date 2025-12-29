# app/services/brain/engine.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.services.brain.ai_hook import AIHook


@dataclass
class BrainEngine:
    """
    Единый мозг: Router всегда зовёт brain.reply(...)
    Здесь решаем: AI ON/OFF, какая модель, и как отвечать (живой диалог, не шаблоны).
    """
    store: Any
    profiles: Any
    settings: Any

    def _ai(self) -> Tuple[Optional[AIHook], str]:
        # Фича-флаг
        if not getattr(self.settings, "ai_enabled", True):
            return None, "AI_ENABLED=0"

        # Ключ
        key = (getattr(self.settings, "openai_api_key", "") or "").strip()
        if not key:
            return None, "OPENAI_API_KEY missing"

        # Модель
        model = (getattr(self.settings, "openai_model", "gpt-4.1-mini") or "gpt-4.1-mini").strip()
        return AIHook(api_key=key, model=model), "OK"

    async def reply(self, *, text: str, profile: Dict[str, Any], history: List[dict]) -> str:
        """
        Возвращает строку ответа.
        ВАЖНО: async, чтобы OpenAI не блокировал FastAPI event loop.
        """
        ai, reason = self._ai()
        if not ai:
            # Не “молчим”, а отдаём понятный диагноз
            return (
                "🧠 ИИ: OFF\n"
                f"Причина: {reason}\n\n"
                "Проверь Render → Environment:\n"
                "• OPENAI_API_KEY=...\n"
                "• AI_ENABLED=1\n"
                "• OPENAI_MODEL=gpt-4.1-mini\n"
                "И сделай Restart сервиса после изменения ENV."
            )

        # Живой ответ от ИИ
        return await ai.generate(profile=profile, history=history, user_text=text)
