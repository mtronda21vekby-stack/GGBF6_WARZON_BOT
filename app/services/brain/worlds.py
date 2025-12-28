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
        if style == "demon":
            return (
                "WARZONE — DEMON TIMEMATE\n"
                "ПОЗИЦИЯ. РОТАЦИЯ. ВЫЖИВАНИЕ.\n\n"
                "Если ты стрелял без укрытия — ты ошибся.\n"
                "Если дрался в газе — ты ошибся.\n\n"
                "Думай как последний сквад."
            )
        if style == "pro":
            return (
                "WARZONE — PRO\n"
                "• Контроль высоты\n"
                "• Ротация раньше газа\n"
                "• Игра от укрытий"
            )
        return "WARZONE — NORMAL\nСначала позиция, потом стрельба."


class BF6World(BaseWorld):
    name = "bf6"

    def analyze(self, text: str, profile, style: str, memory) -> str:
        if style == "demon":
            return (
                "BF6 — DEMON TEAMMATE\n"
                "OBJECTIVE ИЛИ НИЧЕГО.\n\n"
                "Фраг без давления — мусор.\n"
                "Сквад без синхры — смерть."
            )
        if style == "pro":
            return (
                "BF6 — PRO\n"
                "• Играй от точки\n"
                "• Дави после utility\n"
                "• Держи сквад"
            )
        return "BF6 — NORMAL\nИграй objective."


class BO7World(BaseWorld):
    name = "bo7"

    def analyze(self, text: str, profile, style: str, memory) -> str:
        if style == "demon":
            return (
                "BO7 — DEMON TEAMMATE\n"
                "СПАВНЫ. ТАЙМИНГ. ТРЕЙД.\n\n"
                "Соло-пик без трейда — ошибка.\n"
                "Ты обязан читать спавн."
            )
        if style == "pro":
            return (
                "BO7 — PRO\n"
                "• Контроль спавнов\n"
                "• Pre-aim\n"
                "• Тайминги"
            )
        return "BO7 — NORMAL\nДержи позиции."
