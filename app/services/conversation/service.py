# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ConversationService:
    """Single intelligence entrypoint for Telegram and Mini App."""

    brain: Any

    def reply(self, *, text: str, profile: dict, history: list[dict]) -> str:
        return self.brain.reply(text=text, profile=profile, history=history)
