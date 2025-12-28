# app/services/brain/engine.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.services.brain.ai_hook import AIHook


@dataclass
class BrainEngine:
    store: Any
    profiles: Any
    settings: Any

    def _ai(self) -> tuple[Optional[AIHook], str]:
        if not getattr(self.settings, "ai_enabled", True):
            return None, "ai_enabled=False"

        key = (getattr(self.settings, "openai_api_key", "") or "").strip()
        if not key:
            return None, "OPENAI_API_KEY missing"

        model = (getattr(self.settings, "openai_model", "gpt-4.1-mini") or "gpt-4.1-mini").strip()
        return AIHook(api_key=key, model=model), "OK"

    def reply(self, *, text: str, profile: Dict[str, Any], history: List[dict]) -> str:
        ai, reason = self._ai()
        if not ai:
            return (
                "🧠 AI: OFF\n"
                f"Reason: {reason}\n\n"
                "Fix (Render ENV): set OPENAI_API_KEY\n"
                "Then redeploy.\n"
            )
        return ai.generate(profile=profile, history=history, user_text=text)
