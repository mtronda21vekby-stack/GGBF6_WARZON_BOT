from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.crown_core.contracts import CrownSurface


class CrownSkillKind(str, Enum):
    CORE_READ = "core_read"
    CORE_MUTATION = "core_mutation"
    TELEGRAM_PRESENTATION = "telegram_presentation"
    WEB_PRESENTATION = "web_presentation"
    SERVER_TOOL = "server_tool"
    SENSITIVE = "sensitive"
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
                CrownSkillKind.CORE_READ,
                True,
                frozenset(CrownSurface),
            ),
            CrownSkill(
                "player_brain_read",
                CrownSkillKind.CORE_READ,
                True,
                frozenset(CrownSurface),
            ),
            CrownSkill(
                "game_intel_read",
                CrownSkillKind.SERVER_TOOL,
                True,
                frozenset(CrownSurface),
            ),
            CrownSkill(
                "loadout_read",
                CrownSkillKind.CORE_READ,
                True,
                frozenset(CrownSurface),
            ),
            CrownSkill(
                "training_summary_read",
                CrownSkillKind.CORE_READ,
                True,
                frozenset(CrownSurface),
            ),
            CrownSkill(
                "history_summary_read",
                CrownSkillKind.CORE_READ,
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

    def permits_read(self, identifier: str, surface: CrownSurface) -> bool:
        return any(
            skill.identifier == identifier
            and skill.read_only
            and surface in skill.surfaces
            for skill in self._skills
        )
