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
    analysis_report_id: UUID | None = None


@dataclass(frozen=True)
class CrownAnalyzeItem:
    title: str
    detail: str
    category: str = "general"

    def projection(self) -> dict[str, str]:
        return {"title": self.title, "detail": self.detail, "category": self.category}


@dataclass(frozen=True)
class CrownAnalyzeEvidence:
    observation: str
    visible_region: str = ""

    def projection(self) -> dict[str, str]:
        result = {"observation": self.observation}
        if self.visible_region:
            result["visible_region"] = self.visible_region
        return result


@dataclass(frozen=True)
class CrownAnalyzeReport:
    report_id: UUID
    created_at: str
    media_kind: str
    summary: str
    findings: tuple[CrownAnalyzeItem, ...]
    recommendations: tuple[CrownAnalyzeItem, ...]
    warnings: tuple[str, ...]
    evidence: tuple[CrownAnalyzeEvidence, ...]
    follow_up_suggestions: tuple[str, ...]
    question: str = ""

    def projection(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "id": str(self.report_id),
            "created_at": self.created_at,
            "media_kind": self.media_kind,
            "summary": self.summary,
            "findings": [item.projection() for item in self.findings],
            "recommendations": [item.projection() for item in self.recommendations],
            "warnings": list(self.warnings),
            "evidence": [item.projection() for item in self.evidence],
            "follow_up_suggestions": list(self.follow_up_suggestions),
            "question": self.question,
            "provenance": {"response_source": "REAL_BACKEND", "provider_path": "shared_crown_multimodal"},
        }


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
