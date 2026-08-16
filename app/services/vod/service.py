# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VODRequest:
    timecodes: list[str]
    note: str = ""
    has_media: bool = False


class VODAnalysisService:
    """Capability boundary for current text/timestamp VOD and future media vision."""

    def build_analysis_prompt(self, request: VODRequest) -> str:
        times = ", ".join(x for x in request.timecodes if x) or "не указаны"
        if request.has_media:
            capability = "Media is attached, but frame analysis requires a configured vision provider."
        else:
            capability = "Видео не анализировалось: работай только по таймкодам и описанию игрока."
        return (
            f"{capability}\n"
            f"Таймкоды: {times}\n"
            f"Описание: {request.note or '—'}\n"
            "Для каждого эпизода: решение -> ошибка -> лучший вариант -> cue на следующий раз."
        )
