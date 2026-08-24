from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.crown_core.contracts import CrownSurface


class CrownSkillKind(str, Enum):
    CORE = "core"
    SERVER_TOOL = "server_tool"
    SURFACE_PRESENTATION = "surface_presentation"
    LEGACY = "legacy"


@dataclass(frozen=True)
class CrownSkill:
    identifier: str
    kind: CrownSkillKind
    read_only: bool
    surfaces: frozenset[CrownSurface]


class CrownSkillRegistry:
    """Explicit allow-list; adapters cannot expose arbitrary bot handlers."""

    def __init__(self, skills: tuple[CrownSkill, ...] | None = None) -> None:
        self._skills = skills or (
            CrownSkill(
                "conversation",
                CrownSkillKind.CORE,
                True,
                frozenset(CrownSurface),
            ),
            CrownSkill(
                "player_brain",
                CrownSkillKind.CORE,
                True,
                frozenset(CrownSurface),
            ),
            CrownSkill(
                "game_intelligence",
                CrownSkillKind.SERVER_TOOL,
                True,
                frozenset(CrownSurface),
            ),
        )

    def capabilities(self, surface: CrownSurface) -> tuple[str, ...]:
        return tuple(
            skill.identifier
            for skill in self._skills
            if skill.read_only and surface in skill.surfaces
        )
