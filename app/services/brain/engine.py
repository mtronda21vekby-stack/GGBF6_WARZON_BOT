# app/services/brain/engine.py
from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Tuple

from app.observability.quality import quality_telemetry
from app.services.brain.ai_hook import AIHook
from app.services.brain.crown_intel_runtime import get_free_official_provider
from app.services.brain.intents import classify_intent
from app.services.brain.knowledge_context import (
    CompositeKnowledgeProvider,
    KnowledgeProvider,
    KnowledgeRequest,
    StaticKnowledgeProvider,
)
from app.services.brain.quality import currentness_blocked_response, enforce_response_limit
from app.services.brain.response_policy import get_response_policy


log = logging.getLogger("bco.intelligence")
PartialCallback = Callable[[str, dict[str, Any]], None]


@dataclass
class BrainEngine:
    store: Any
    profiles: Any
    settings: Any
    knowledge_provider: KnowledgeProvider | None = None

    def __post_init__(self) -> None:
        if self.knowledge_provider is not None:
            return
        providers: list[KnowledgeProvider] = []
        if bool(getattr(self.settings, "live_knowledge_enabled", True)):
            providers.append(
                get_free_official_provider(
                    ttl_s=getattr(self.settings, "live_knowledge_ttl_s", 900),
                    timeout_s=getattr(self.settings, "live_knowledge_timeout_s", 6.0),
                )
            )
        providers.append(StaticKnowledgeProvider())
        self.knowledge_provider = CompositeKnowledgeProvider(providers)

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
        on_partial: PartialCallback | None = None,
    ) -> str:
        started = time.monotonic()
        request_id = uuid.uuid4().hex[:12]
        intent = classify_intent(text, profile)
        policy = get_response_policy(intent, profile)
        knowledge = self.knowledge_provider.query(
            KnowledgeRequest(intent=intent, text=text, profile=profile)
        ) if self.knowledge_provider else None
        knowledge_name = knowledge.confidence.value if knowledge else "UNKNOWN"

        if intent.needs_current_data and (knowledge is None or not knowledge.is_verified_current):
            fallback_knowledge = knowledge or CompositeKnowledgeProvider().query(
                KnowledgeRequest(intent=intent, text=text, profile=profile)
            )
            result = currentness_blocked_response(fallback_knowledge)
            latency = int((time.monotonic() - started) * 1000)
            quality_telemetry.record_reply(
                intent=intent.intent.value,
                latency_ms=latency,
                knowledge=knowledge_name,
                outcome="currentness_blocked",
                currentness_blocked=True,
            )
            log.info(
                "bco_reply request_id=%s intent=%s game=%s voice=%s brain=%s model=%s "
                "latency_ms=%d knowledge=%s response_len=%d current_gate=blocked",
                request_id, intent.intent.value, profile.get("game"), profile.get("voice"),
                profile.get("difficulty"), getattr(self.settings, "openai_model", "?"),
                latency, knowledge_name, len(result),
            )
            return result

        ai, reason = self._ai()
        if not ai:
            result = (
                "🧠 ИИ: OFF\n"
                f"Причина: {reason}\n\n"
                "Нужны Environment variables:\n"
                "• OPENAI_API_KEY\n"
                "• AI_ENABLED=1\n"
                "• OPENAI_MODEL"
            )
            quality_telemetry.record_reply(
                intent=intent.intent.value,
                latency_ms=int((time.monotonic() - started) * 1000),
                knowledge=knowledge_name,
                outcome="disabled",
            )
            return result

        error_class = ""
        result = ""
        meta: dict[str, Any] = {}
        try:
            generated = ai.generate(
                profile=profile,
                history=history or [],
                user_text=text,
                intent_result=intent,
                policy=policy,
                knowledge=knowledge,
                player_context=dict(player_context or profile),
                on_partial=on_partial,
            )
            meta = dict(ai.last_generation_meta or {})
            result = enforce_response_limit(generated, policy)
            if on_partial is not None and result != generated:
                try:
                    on_partial(result, {"phase": "final", "reset": True, "limited": True})
                except Exception:
                    pass
            return result
        except Exception as exc:
            error_class = type(exc).__name__
            meta = dict(getattr(ai, "last_generation_meta", {}) or {})
            meta["outcome"] = "error"
            meta["error_class"] = error_class
            result = (
                "🧠 ИИ: ERROR\n"
                f"{error_class}: {exc}\n\n"
                "Проверь OPENAI_API_KEY / OPENAI_MODEL."
            )
            return result
        finally:
            latency = int((time.monotonic() - started) * 1000)
            outcome = str(meta.get("outcome") or ("error" if error_class else "ok"))
            quality_telemetry.record_reply(
                intent=intent.intent.value,
                latency_ms=latency,
                knowledge=knowledge_name,
                outcome=outcome,
                attempts=int(meta.get("attempts") or 1),
                anti_repeat_retry=bool(meta.get("anti_repeat_retry")),
            )
            log.info(
                "bco_reply request_id=%s intent=%s game=%s voice=%s brain=%s model=%s "
                "latency_ms=%d knowledge=%s attempts=%d anti_repeat=%s streamed=%s chunks=%d "
                "outcome=%s response_len=%d error=%s",
                request_id, intent.intent.value, profile.get("game"), profile.get("voice"),
                profile.get("difficulty"), getattr(self.settings, "openai_model", "?"),
                latency, knowledge_name, int(meta.get("attempts") or 1),
                bool(meta.get("anti_repeat_retry")), bool(meta.get("streamed")),
                int(meta.get("stream_chunks") or 0), outcome, len(result),
                str(meta.get("error_class") or error_class or "none"),
            )
