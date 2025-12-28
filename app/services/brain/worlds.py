# -*- coding: utf-8 -*-
from __future__ import annotations
from app.services.brain.knowledge import TOP_RULES


class BaseWorld:
    name = "base"

    def analyze(self, text: str, profile, style: str, memory) -> str:
        return "Опиши ситуацию."


class WarzoneWorld(BaseWorld):
    name = "warzone"

    def analyze(self, text: str, profile, style: str, memory) -> str:
        rules = TOP_RULES["warzone"]
        return self._build(style, rules, memory, profile.user_id)

    def _build(self, style, rules, memory, uid):
        if style == "demon":
            return (
                "WARZONE — DEMON\n"
                "ПОЗИЦИЯ. РОТАЦИЯ. ВЫЖИВАНИЕ.\n\n"
                f"НЕ ДЕЛАЙ:\n- " + "\n- ".join(rules["never"]) +
                self._memory(memory, uid)
            )
        if style == "pro":
            return (
                "WARZONE — PRO\n\n"
                f"ВСЕГДА:\n- " + "\n- ".join(rules["always"])
            )
        return (
            "WARZONE — NORMAL\n\n"
            "Сначала позиция, потом стрельба."
        )

    def _memory(self, memory, uid):
        err = memory.common_error(uid)
        return f"\n\nТВОЯ ПОВТОРЯЮЩАЯСЯ ОШИБКА:\n{err}" if err else ""


class BF6World(BaseWorld):
    name = "bf6"

    def analyze(self, text: str, profile, style: str, memory) -> str:
        rules = TOP_RULES["bf6"]
        if style == "demon":
            return (
                "BF6 — DEMON\n"
                "OBJECTIVE. TEAMPLAY. PRESSURE.\n\n"
                f"NEVER:\n- " + "\n- ".join(rules["never"])
            )
        if style == "pro":
            return (
                "BF6 — PRO\n\n"
                f"ALWAYS:\n- " + "\n- ".join(rules["always"])
            )
        return "BF6 — NORMAL\nPlay objective."


class BO7World(BaseWorld):
    name = "bo7"

    def analyze(self, text: str, profile, style: str, memory) -> str:
        rules = TOP_RULES["bo7"]
        if style == "demon":
            return (
                "BO7 — DEMON\n"
                "SPAWNS. TIMING. TRADES.\n\n"
                f"НЕ ДЕЛАЙ:\n- " + "\n- ".join(rules["never"])
            )
        if style == "pro":
            return (
                "BO7 — PRO\n\n"
                f"ВСЕГДА:\n- " + "\n- ".join(rules["always"])
            )
        return "BO7 — NORMAL\nДержи спавны."
