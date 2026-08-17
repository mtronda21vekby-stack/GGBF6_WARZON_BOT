# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

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


@dataclass
class ConversationService:
    """Single intelligence entrypoint for Telegram and Mini App.

    Telegram Router already writes the user/assistant pair around this call.
    Verified Mini App calls do not, so this service fills that gap without
    duplicating Telegram history.
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

    def reply(
        self,
        *,
        text: str,
        profile: dict,
        history: list[dict],
        on_partial: PartialCallback | None = None,
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
