# -*- coding: utf-8 -*-
from __future__ import annotations


def detect_situation(text: str) -> str | None:
    t = text.lower()

    if any(x in t for x in ["зажали", "узко", "не вышел", "угол"]):
        return "bad_position"

    if any(x in t for x in ["толпа", "окружили", "много", "орда"]):
        return "overwhelmed"

    if any(x in t for x in ["спец", "элит", "босс", "жирный"]):
        return "special_enemy"

    if any(x in t for x in ["пушнул", "побежал", "раш"]):
        return "overaggressive"

    return None
