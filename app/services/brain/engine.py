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

    def reply(self, *, text: str, profile: Dict[str, Any], history: List[dict]) -> str:
        ai, reason = self._ai()
        if not ai:
            return (
                "🧠 ИИ: OFF\n"
                f"Причина: {reason}\n\n"
                "Render ENV (Environment):\n"
                "• OPENAI_API_KEY=...\n"
                "• AI_ENABLED=1\n"
                "• OPENAI_MODEL=gpt-4.1-mini (или другой)\n"
            )

        # нормализуем историю до списка сообщений
        hist = history or []
        try:
            return ai.generate(profile=profile, history=hist, user_text=text)
        except Exception as e:
            return (
                "🧠 ИИ: ERROR\n"
                f"{type(e).__name__}: {e}\n\n"
                "Проверь:\n"
                "• OPENAI_API_KEY\n"
                "• AI_ENABLED=1\n"
                "• OPENAI_MODEL\n"
            )
