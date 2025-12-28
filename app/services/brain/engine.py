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

    def _ai(self) -> Optional[AIHook]:
        if not getattr(self.settings, "ai_enabled", True):
            return None
        key = (getattr(self.settings, "openai_api_key", "") or "").strip()
        if not key:
            return None
        model = (getattr(self.settings, "openai_model", "gpt-4.1-mini") or "gpt-4.1-mini").strip()
        return AIHook(api_key=key, model=model)

    def reply(self, *, text: str, profile: Dict[str, Any], history: List[dict]) -> str:
        ai = self._ai()
        if not ai:
            # если ключа нет — умный офлайн фолбэк, но НЕ тупой цикл
            return (
                "🧠 AI пока OFF (нет OPENAI_API_KEY).\n"
                "Скинь одной строкой:\n"
                "Игра | платформа | input | роль/класс | от чего умер | дистанция (close/mid/long)\n"
                "и я дам «СЕЙЧАС / ДАЛЬШЕ»."
            )
        return ai.generate(profile=profile, history=history, user_text=text)
