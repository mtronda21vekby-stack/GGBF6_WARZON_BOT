# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExtractedPlayerMemory:
    profile_patch: dict[str, Any] = field(default_factory=dict)
    mistakes: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


_KD_RE = re.compile(r"(?:\bkd\b|\bk/d\b|\bкд\b)\s*[:=]?\s*(\d{1,2}(?:[.,]\d{1,2})?)", re.I)
_RANK_RE = re.compile(r"(?:мой\s+)?(?:rank|ранг)\s*[:=]?\s*([\wА-Яа-яЁё -]{2,32})", re.I)
_KILLS_RE = re.compile(r"\b(\d{1,3})\s*(?:kills?|кил(?:л|ла|лов|ы)?)\b", re.I)
_PLACE_RE = re.compile(r"(?:топ|top|место|place)\s*[-:#]?\s*(\d{1,3})", re.I)
_ACCURACY_RE = re.compile(r"(?:accuracy|acc|точност(?:ь|и))\s*[:=]?\s*(\d{1,3}(?:[.,]\d+)?)\s*%?", re.I)


def _clean_capture(value: str) -> str:
    return " ".join((value or "").strip(" .,!?:;\n\t").split())


def extract_player_memory(text: str) -> ExtractedPlayerMemory:
    raw = str(text or "").strip()
    low = raw.lower()
    out = ExtractedPlayerMemory()

    m = _KD_RE.search(raw)
    if m:
        try:
            kd = float(m.group(1).replace(",", "."))
            if 0 <= kd <= 20:
                out.profile_patch["kd"] = kd
        except Exception:
            pass

    m = _RANK_RE.search(raw)
    if m:
        rank = _clean_capture(m.group(1))
        if rank and len(rank) <= 32:
            out.profile_patch["rank"] = rank

    # Store a goal only when the user explicitly frames it as a goal.
    for marker in ("моя цель", "цель:", "my goal", "хочу улучшить", "хочу поднять"):
        if marker in low:
            idx = low.find(marker)
            goal = _clean_capture(raw[idx + len(marker):])[:160]
            if goal:
                out.profile_patch["current_goal"] = goal
            break

    for marker in ("любимая пушка", "любимое оружие", "favorite weapon"):
        if marker in low:
            idx = low.find(marker)
            weapon = _clean_capture(raw[idx + len(marker):])[:64]
            if weapon:
                out.profile_patch["preferred_weapons"] = [weapon]
            break

    # Conservative mistake taxonomy: only explicit evidence from the user's text.
    if ("ротац" in low and any(x in low for x in ("позд", "не усп", "газ", "опоз"))):
        out.mistakes.append("Поздняя ротация")
    if any(x in low for x in ("репик", "повторно пик", "тот же угол", "снова вышел в тот же")):
        out.mistakes.append("Повторный пик одного угла")
    if any(x in low for x in ("соло пуш", "соло-пуш", "пушнул один", "залетел один", "рашнул один")):
        out.mistakes.append("Соло-пуш без трейда/инфы")
    if any(x in low for x in ("в открытом", "без укрытия", "в поле", "на открытом")):
        out.mistakes.append("Файт без достаточного укрытия")
    if any(x in low for x in ("паник", "руки тряс", "зажал спрей", "запаников")):
        out.mistakes.append("Паника под давлением")
    if any(x in low for x in ("полез за килл", "жадн", "добить килл", "погнался за")):
        out.mistakes.append("Жадность за киллом вместо позиции")

    m = _KILLS_RE.search(raw)
    if m:
        out.metrics["kills"] = int(m.group(1))
    m = _PLACE_RE.search(raw)
    if m:
        out.metrics["placement"] = int(m.group(1))
    m = _ACCURACY_RE.search(raw)
    if m:
        try:
            value = float(m.group(1).replace(",", "."))
            if 0 <= value <= 100:
                out.metrics["accuracy_pct"] = value
        except Exception:
            pass

    # Keep deterministic order without duplicates.
    out.mistakes = list(dict.fromkeys(out.mistakes))
    return out
