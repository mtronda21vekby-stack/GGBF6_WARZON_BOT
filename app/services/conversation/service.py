# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.player_memory.service import PlayerMemoryService


@dataclass
class ConversationService:
    """Single intelligence entrypoint for Telegram and Mini App."""

    brain: Any
    store: Any = None
    profiles: Any = None

    def __post_init__(self) -> None:
        self.player_memory = (
            PlayerMemoryService(store=self.store, profiles=self.profiles)
            if self.store is not None and self.profiles is not None
            else None
        )

    def reply(self, *, text: str, profile: dict, history: list[dict]) -> str:
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

        player_context = dict(profile or {})
        if trusted and chat_id is not None and self.player_memory is not None:
            try:
                player_context = self.player_memory.context(chat_id, profile)
            except Exception:
                player_context = dict(profile or {})

        result = self.brain.reply(
            text=text,
            profile=profile,
            history=history,
            player_context=player_context,
        )

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
