# -*- coding: utf-8 -*-
from __future__ import annotations
import random


DIALOGUES = {
    "normal": {
        "bad_position": [
            "Ты выбрал плохую позицию. Давай исправим.",
            "Здесь нужно было оставить выход."
        ],
        "overaggressive": [
            "Ты поспешил. Возьми паузу.",
        ],
    },
    "pro": {
        "bad_position": [
            "Позиция слабая. Ты сам себя загнал.",
        ],
        "overwhelmed": [
            "Ты дал орде собраться. Контроль потерян.",
        ],
    },
    "demon": {
        "bad_position": [
            "Ты сам себя убил.",
            "Узко. Без выхода. Это ошибка.",
        ],
        "overaggressive": [
            "Раш без инфы — мусорное решение.",
        ],
        "overwhelmed": [
            "Ты потерял контроль. Это конец.",
        ],
        "special_enemy": [
            "Ты полез на спеца без плана.",
        ],
    },
}


def get_dialogue(style: str, situation: str) -> str:
    pool = DIALOGUES.get(style, {}).get(situation)
    if not pool:
        return ""
    return random.choice(pool)
