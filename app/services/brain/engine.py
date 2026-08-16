# app/services/brain/engine.py
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Tuple

from app.services.brain.ai_hook import AIHook
from app.services.brain.intents import classify_intent
from app.services.brain.knowledge_context import (
    CompositeKnowledgeProvider,
    KnowledgeProvider,
    KnowledgeRequest,
    StaticKnowledgeProvider,
)
from app.services.brain.quality import currentness_blocked_response, enforce_response_limit
from app.services.brain.response_policy import get_response_policy
from app.services.knowledge.official_snapshots import OfficialSnapshotProvider


log = logging.getLogger("bco.intelligence")


@dataclass
class BrainEngine:
    store: Any
    profiles: Any
    settings: Any
    knowledge_provider: KnowledgeProvider | None = None

    def __post_init__(self) -> None:
        if self.knowledge_provider is None:
            # Current official snapshots are queried first. They only return
            # VERIFIED_CURRENT while their verification TTL is valid. Static
            # repository knowledge remains the fallback for non-current tasks.
            self.knowledge_provider = CompositeKnowledgeProvider([
                OfficialSnapshotProvider(),
                StaticKnowledgeProvider(),
            ])

    def _ai(self) -> Tuple[Optional[AIHook], str]:
        if not getattr(self.settings, "ai_enabled", True):
            return None, "AI_ENABLED=0"
        key = (getattr(self.settings, "openai_api_key", "") or "").strip()
        if not key:
            return None, "OPENAI_API_KEY missing"
        model = (getattr(self.settings, "openai_model", "gpt-4.1-mini") or "gpt-4.1-mini").strip()
        return AIHook(api_key=key, model=model), "OK"

    def reply(
        self,
        *,
        text: str,
        profile: dict[str, Any],
        history: list[dict],
        player_context: Mapping[str, Any] | None = None,
    ) -> str:
        started = time.monotonic()
        request_id = uuid.uuid4().hex[:12]
        intent = classify_intent(text, profile)
        policy = get_response_policy(intent, profile)
        knowledge = self.knowledge_provider.query(
            KnowledgeRequest(intent=intent, text=text, profile=profile)
        ) if self.knowledge_provider else None

        if intent.needs_current_data and (knowledge is None or not knowledge.is_verified_current):
            fallback_knowledge = knowledge or CompositeKnowledgeProvider().query(
                KnowledgeRequest(intent=intent, text=text, profile=profile)
            )
            result = currentness_blocked_response(fallback_knowledge)
            log.info(
                "bco_reply request_id=%s intent=%s game=%s voice=%s brain=%s model=%s "
                "latency_ms=%d knowledge=%s response_len=%d current_gate=blocked",
                request_id, intent.intent.value, profile.get("game"), profile.get("voice"),
                profile.get("difficulty"), getattr(self.settings, "openai_model", "?"),
                int((time.monotonic() - started) * 1000),
                (knowledge.confidence.value if knowledge else "UNKNOWN"), len(result),
            )
            return result

        ai, reason = self._ai()
        if not ai:
            return (
                "🧠 ИИ: OFF\n"
                f"Причина: {reason}\n\n"
                "Нужны Environment variables:\n"
                "• OPENAI_API_KEY\n"
                "• AI_ENABLED=1\n"
                "• OPENAI_MODEL"
            )

        error_class = ""
        try:
            result = ai.generate(
                profile=profile,
                history=history or [],
                user_text=text,
                intent_result=intent,
                policy=policy,
                knowledge=knowledge,
                player_context=dict(player_context or profile),
            )
            return enforce_response_limit(result, policy)
        except Exception as exc:
            error_class = type(exc).__name__
            return (
                "🧠 ИИ: ERROR\n"
                f"{error_class}: {exc}\n\n"
                "Проверь OPENAI_API_KEY / OPENAI_MODEL."
            )
        finally:
            log.info(
                "bco_reply request_id=%s intent=%s game=%s voice=%s brain=%s model=%s "
                "latency_ms=%d knowledge=%s error=%s",
                request_id, intent.intent.value, profile.get("game"), profile.get("voice"),
                profile.get("difficulty"), getattr(self.settings, "openai_model", "?"),
                int((time.monotonic() - started) * 1000),
                (knowledge.confidence.value if knowledge else "UNKNOWN"), error_class or "none",
            )
