# -*- coding: utf-8 -*-
from __future__ import annotations


class BaseWorld:
    name = "base"

    def intro(self) -> str:
        return ""

    def analyze(self, text: str, profile) -> str:
        return "Опиши ситуацию подробнее."


# -------- WARZONE --------
class WarzoneWorld(BaseWorld):
    name = "warzone"

    def intro(self) -> str:
        return "🔥 WARZONE — мышление через позицию, тайминги, выживание."

    def analyze(self, text: str, profile) -> str:
        return (
            "WARZONE ANALYSIS:\n"
            "• Проверь позицию (высота / укрытие)\n"
            "• Где был газ?\n"
            "• Тайминг ротации?\n\n"
            "Опиши:\n"
            "дистанция | соло/сквад | газ"
        )


# -------- BF6 --------
class BF6World(BaseWorld):
    name = "bf6"

    def intro(self) -> str:
        return "🪖 BF6 — objective, teamplay, pressure."

    def analyze(self, text: str, profile) -> str:
        return (
            "BF6 ANALYSIS:\n"
            "• Objective status?\n"
            "• Squad positioning?\n"
            "• Tickets pressure?\n\n"
            "Describe:\n"
            "role | objective | death reason"
        )


# -------- BO7 --------
class BO7World(BaseWorld):
    name = "bo7"

    def intro(self) -> str:
        return "💣 BO7 — дуэли, спавны, тайминги."

    def analyze(self, text: str, profile) -> str:
        return (
            "BO7 ANALYSIS:\n"
            "• Spawn control?\n"
            "• Trade or solo death?\n"
            "• Pre-aim or rush?\n\n"
            "Опиши:\n"
            "карта | позиция | как умер"
        )
