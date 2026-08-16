# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.services.brain.intents import Intent, IntentResult


@dataclass(frozen=True)
class ResponsePolicy:
    depth: str
    max_chars: int
    format_hint: str
    allow_clarification: bool = True
    max_clarifying_questions: int = 1
    include_sources: bool = False
    include_training: bool = False
    require_uncertainty: bool = False


_BASE: dict[Intent, ResponsePolicy] = {
    Intent.CASUAL: ResponsePolicy("short", 700, "human, conversational, no coaching template", False, 0),
    Intent.SYSTEM_HELP: ResponsePolicy("short", 1200, "capabilities and next action", False, 0),
    Intent.GAME_TACTICS: ResponsePolicy("medium", 1800, "decision -> reason -> next-fight rule"),
    Intent.DEATH_ANALYSIS: ResponsePolicy("deep", 2200, "root cause -> mistake -> next-fight correction -> metric"),
    Intent.POSITIONING: ResponsePolicy("medium", 1900, "position rule -> timing -> safe fallback"),
    Intent.AIM: ResponsePolicy("medium", 1800, "mechanical diagnosis -> correction -> measurable drill", include_training=True),
    Intent.MOVEMENT: ResponsePolicy("medium", 1800, "movement error -> combat purpose -> drill", include_training=True),
    Intent.LOADOUT: ResponsePolicy("medium", 2200, "setup -> why -> trade-offs -> who it fits", include_sources=True),
    Intent.META_CURRENT: ResponsePolicy(
        "medium", 2200, "freshness -> verified facts -> recommendation",
        include_sources=True, require_uncertainty=True,
    ),
    Intent.PATCH_CURRENT: ResponsePolicy(
        "medium", 2200, "freshness -> verified changes -> gameplay impact",
        include_sources=True, require_uncertainty=True,
    ),
    Intent.GAME_SETTINGS: ResponsePolicy("medium", 2300, "recommended settings -> rationale -> tuning range", include_sources=True),
    Intent.TRAINING: ResponsePolicy("deep", 2600, "objective -> drill blocks -> metric -> stop condition", include_training=True),
    Intent.ZOMBIES: ResponsePolicy("medium", 2400, "map-specific ordered steps -> fail condition -> recovery"),
    Intent.VOD_TEXT_ANALYSIS: ResponsePolicy("deep", 2600, "timestamp -> decision -> error -> alternative -> next-time cue"),
    Intent.PROFILE: ResponsePolicy("short", 1400, "known profile -> unknown fields -> useful next field", False, 0),
    Intent.PLAYER_PROGRESS: ResponsePolicy("deep", 2400, "trend -> evidence -> recurring pattern -> next objective"),
    Intent.UNKNOWN: ResponsePolicy("medium", 1700, "answer the likely request; clarify only if outcome changes"),
}


def get_response_policy(intent: IntentResult, profile: Mapping[str, Any] | None = None) -> ResponsePolicy:
    base = _BASE[intent.intent]
    profile = profile or {}
    voice = str(profile.get("voice") or profile.get("voice_mode") or "TEAMMATE").upper()
    brain = str(profile.get("difficulty") or profile.get("brain_mode") or "Normal").upper()

    depth = base.depth
    max_chars = base.max_chars

    if voice == "COACH" and depth != "short":
        depth = "deep"
        max_chars = min(3200, max_chars + 350)

    if brain == "DEMON" and depth == "medium":
        depth = "deep"
    elif brain == "NORMAL" and max_chars > 2400:
        max_chars = 2400

    return ResponsePolicy(
        depth=depth,
        max_chars=max_chars,
        format_hint=base.format_hint,
        allow_clarification=base.allow_clarification,
        max_clarifying_questions=base.max_clarifying_questions,
        include_sources=base.include_sources,
        include_training=base.include_training,
        require_uncertainty=base.require_uncertainty,
    )
