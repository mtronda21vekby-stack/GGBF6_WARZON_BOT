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


class CrownCoreFailure(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code
