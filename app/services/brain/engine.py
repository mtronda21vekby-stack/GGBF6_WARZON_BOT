# app/services/brain/engine.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.services.brain.ai_hook import AIHook


@dataclass
class BrainEngine:
    store: Any
    profiles: Any
    settings: Any

    def _ai(self) -> Tuple[Optional[AIHook], str]:
        if not getattr(self.settings, "ai_enabled", True):
            return None, "AI_ENABLED=0"

        key = (getattr(self.settings, "openai_api_key", "") or "").strip()
        if not key:
            return None, "OPENAI_API_KEY missing"

        model = (getattr(self.settings, "openai_model", "gpt-4.1-mini") or "gpt-4.1-mini").strip()
        return AIHook(api_key=key, model=model), "OK"

    async def reply(self, *, text: str, profile: Dict[str, Any], history: List[dict]) -> str:
        """
        ВАЖНО: async — чтобы AIHook.generate (async) работал нормально и бот не молчал.
        """
        ai, reason = self._ai()
        if not ai:
            return (
                "🧠 ИИ: OFF\n"
                f"Причина: {reason}\n\n"
                "Render ENV проверь:\n"
                "• OPENAI_API_KEY\n"
                "• AI_ENABLED=1\n"
                "• OPENAI_MODEL=gpt-4.1-mini\n"
                "И сделай Restart сервиса после правок.\n"
            )

        # AIHook.generate — async
        return await ai.generate(profile=profile, history=history, user_text=text)
