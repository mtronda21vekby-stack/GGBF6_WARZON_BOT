# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


@dataclass
class PlayerIntelligence:
    game: str | None = None
    mode: str | None = None
    platform: str | None = None
    input: str | None = None
    role: str | None = None
    rank: str | None = None
    kd: float | None = None
    playstyle: str | None = None
    preferred_weapons: list[str] = field(default_factory=list)
    favorite_modes: list[str] = field(default_factory=list)
    current_goal: str | None = None

    aim_score: float | None = None
    movement_score: float | None = None
    positioning_score: float | None = None
    decision_score: float | None = None
    comms_score: float | None = None

    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    recurring_mistakes: list[str] = field(default_factory=list)
    tilt_patterns: list[str] = field(default_factory=list)

    training_focus: str | None = None
    weekly_focus: str | None = None
    last_session_summary: str | None = None
    progress_notes: list[str] = field(default_factory=list)

    preferred_response_depth: str | None = None
    voice_mode: str | None = None
    brain_mode: str | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "PlayerIntelligence":
        data = data or {}
        allowed = cls.__dataclass_fields__.keys()
        kwargs = {k: data[k] for k in allowed if k in data and data[k] is not None}
        return cls(**kwargs)

    def to_dict(self, *, drop_empty: bool = True) -> dict[str, Any]:
        raw = asdict(self)
        if not drop_empty:
            return raw
        return {k: v for k, v in raw.items() if v not in (None, "", [], {})}
