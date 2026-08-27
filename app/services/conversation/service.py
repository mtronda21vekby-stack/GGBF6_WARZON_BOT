# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.services.operator_intelligence.context import OperatorContextService
from app.services.player_memory.service import PlayerMemoryService


PartialCallback = Callable[[str, dict[str, Any]], None]


def _same_user_tail(history: list[dict], text: str) -> bool:
    if not history:
        return False
    last = history[-1]
    if not isinstance(last, dict):
        return False
    return (
        str(last.get("role") or "").lower() == "user"
        and str(last.get("content") or "").strip() == str(text or "").strip()
    )


def _rate_limit_text(seconds: int) -> str:
    wait = max(1, int(seconds or 1))
    return (
        "⏳ Слишком много AI-запросов подряд. "
        f"Подожди примерно {wait} сек. и отправь следующий запрос."
    )


def _env_on(name: str, default: str = "1") -> bool:
    return os.getenv(name, default).strip().casefold() not in {"0", "false", "off", "no", ""}


@dataclass
class ConversationService:
    """Single intelligence entrypoint for Telegram and Mini App.

    Telegram Router already writes the user/assistant pair around this call.
    Verified Mini App calls do not, so this service fills that gap without
    duplicating Telegram history.

    v26 also projects the server-authoritative Operator Twin into one bounded
    truth-calibrated context. Because Telegram text, accepted voice transcripts
    and the Mini App converge here, all of them receive the same operator state
    without creating a second conversational brain.
    """

    brain: Any
    store: Any = None
    profiles: Any = None
    usage_guard: Any = None

    def __post_init__(self) -> None:
        self.player_memory = (
            PlayerMemoryService(store=self.store, profiles=self.profiles)
            if self.store is not None and self.profiles is not None
            else None
        )
        settings = getattr(self.brain, "settings", None)
        if settings is None:
            # Preserve the exact legacy/test adapter contract. The v26 context
            # bridge belongs to the production BrainEngine, which owns Settings.
            bridge_enabled = False
            operator_enabled = False
            missions_enabled = False
        else:
            bridge_setting = getattr(settings, "operator_context_bridge_enabled", None)
            bridge_enabled = (
                bool(bridge_setting)
                if bridge_setting is not None
                else _env_on("OPERATOR_CONTEXT_BRIDGE_ENABLED")
            )
            operator_enabled = bool(getattr(settings, "operator_intelligence_enabled", True))
            missions_enabled = bool(getattr(settings, "adaptive_mission_control_enabled", True))
        self.operator_context = (
            OperatorContextService(
                store=self.store,
                profiles=self.profiles,
                operator_enabled=operator_enabled,
                missions_enabled=missions_enabled,
            )
            if self.store is not None and self.profiles is not None and bridge_enabled and operator_enabled
            else None
        )

    def reply(
        self,
        *,
        text: str,
        profile: dict,
        history: list[dict],
        on_partial: PartialCallback | None = None,
        server_context: dict[str, Any] | None = None,
    ) -> str:
        trusted = False
        chat_id = None
        if self.profiles is not None and hasattr(self.profiles, "is_trusted_context"):
            try:
                trusted = bool(self.profiles.is_trusted_context(profile))
            except Exception:
                trusted = False
        if trusted:
            try:
                chat_id = int(profile.get("_chat_id"))
            except Exception:
                chat_id = None

        # Enforce cost limits at the canonical AI generation boundary. This
        # protects both Telegram and verified Mini App calls and deliberately
        # happens before Mini App working-memory writes.
        if trusted and chat_id is not None and self.usage_guard is not None:
            try:
                decision = self.usage_guard.check(chat_id, "ai")
                if not bool(getattr(decision, "allowed", True)):
                    return _rate_limit_text(int(getattr(decision, "retry_after_s", 1) or 1))
            except Exception:
                # Guard failures must not take the coaching service down.
                pass

        # Telegram Router inserts current user text before calling the brain.
        # Mini App server context does not. This flag distinguishes the paths.
        caller_manages_working_memory = _same_user_tail(history or [], text)
        if trusted and chat_id is not None and not caller_manages_working_memory and self.store is not None:
            try:
                self.store.add(chat_id, "user", text)
            except Exception:
                pass

        player_context = dict(profile or {})
        if trusted and chat_id is not None and self.player_memory is not None:
            try:
                player_context = self.player_memory.context(chat_id, profile)
            except Exception:
                player_context = dict(profile or {})

        # v26 trust boundary: only a server-resolved Telegram identity can
        # receive persistent Operator Twin context. Fail open to the established
        # Player Intelligence path if the derived operator layer is unavailable.
        if trusted and chat_id is not None and self.operator_context is not None:
            try:
                player_context["operator_context"] = self.operator_context.context(chat_id)
            except Exception:
                pass

        if isinstance(server_context, dict):
            analysis_report = server_context.get("analysis_report")
            if isinstance(analysis_report, dict):
                player_context["analysis_report"] = dict(analysis_report)

        brain_kwargs: dict[str, Any] = {
            "text": text,
            "profile": profile,
            "history": history,
            "player_context": player_context,
        }
        # Do not pass a new optional keyword to legacy/test brain adapters when
        # there is no streaming consumer. Production BrainEngine accepts it;
        # non-streaming implementations keep their previous call contract.
        if on_partial is not None:
            brain_kwargs["on_partial"] = on_partial
        result = self.brain.reply(**brain_kwargs)

        if trusted and chat_id is not None and not caller_manages_working_memory and self.store is not None:
            try:
                self.store.add(chat_id, "assistant", str(result))
            except Exception:
                pass

        if trusted and chat_id is not None and self.player_memory is not None:
            try:
                self.player_memory.observe(
                    chat_id=chat_id,
                    text=text,
                    profile=profile,
                    reply=str(result),
                    trusted=True,
                )
            except Exception:
                pass
        return result
