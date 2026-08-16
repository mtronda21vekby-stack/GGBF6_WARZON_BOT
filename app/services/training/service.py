# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class TrainingPlan:
    objective: str
    blocks: list[str]
    metric: str
    stop_condition: str


class TrainingService:
    """Deterministic training-plan boundary; richer analytics can replace it later."""

    def build(self, *, focus: str, profile: Mapping[str, Any] | None = None) -> TrainingPlan:
        focus = (focus or "hybrid").strip().lower()
        profile = profile or {}
        game = str(profile.get("game") or "FPS")
        objective = f"{game}: improve {focus} without adding decision chaos"
        blocks = [
            "5 min: controlled warm-up at comfortable speed",
            f"10 min: focused {focus} repetitions with one rule only",
            "5 min: match-like application; stop after each mistake and name the cause",
        ]
        metric = "Complete 3 clean repetitions in a row before increasing speed."
        stop = "Stop the drill if mechanics degrade for 3 repetitions; reset instead of grinding bad reps."
        return TrainingPlan(objective, blocks, metric, stop)
