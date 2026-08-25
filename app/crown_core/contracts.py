from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID


class CrownSurface(str, Enum):
    TELEGRAM = "telegram"
    WEB = "web"
    IOS = "ios"


@dataclass(frozen=True)
class CrownPrincipal:
    """Server-resolved product identity. Client payloads never construct this."""

    black_crown_user_id: UUID
    provider: str
    provider_subject: str
    legacy_owner_id: int


@dataclass(frozen=True)
class CrownTurnRequest:
    principal: CrownPrincipal
    surface: CrownSurface
    session_id: UUID
    turn_id: UUID
    text: str
    locale: str
    route: str
    client_context: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class CrownTurnResult:
    display_text: str
    spoken_text: str


@dataclass(frozen=True)
class CrownSkillBlock:
    type: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class CrownSkillResult:
    skill_id: str
    title: str
    summary: str
    blocks: tuple[CrownSkillBlock, ...]
    data: dict[str, Any]
    freshness_timestamp: str
    warnings: tuple[str, ...] = ()
    next_cursor: str | None = None

    def projection(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "title": self.title,
            "summary": self.summary,
            "blocks": [
                {"type": block.type, **dict(block.payload)}
                for block in self.blocks
            ],
            "data": dict(self.data),
            "freshness_timestamp": self.freshness_timestamp,
            "warnings": list(self.warnings),
            "next_cursor": self.next_cursor,
        }


class CrownCoreFailure(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code
