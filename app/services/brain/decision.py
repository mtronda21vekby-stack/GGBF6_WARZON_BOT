# -*- coding: utf-8 -*-
from __future__ import annotations

from app.services.brain.patterns import ROLE_PATTERNS


def detect_bad_decision(game: str, text: str) -> str | None:
    t = text.lower()
    patterns = ROLE_PATTERNS.get(game, {})

    for role, data in patterns.items():
        for bad in data.get("bad", []):
            key = bad.split()[0].lower()
            if key in t:
                return bad

    return None


def build_decision_feedback(game: str, bad_decision: str) -> str:
    return (
        "❌ ПЛОХОЕ РЕШЕНИЕ ОБНАРУЖЕНО:\n"
        f"• {bad_decision}\n\n"
        "Это не уровень топ-игроков.\n"
        "Исправь это действие."
    )
