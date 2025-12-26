# -*- coding: utf-8 -*-
"""
Pattern Engine
Наблюдает за повторяющимися причинами смертей
и иногда выдаёт наблюдение как живой тренер.
"""

from typing import Dict, List, Optional
from collections import Counter
import time

WINDOW = 8
MIN_REPEAT = 3
COOLDOWN = 180

CAUSE_LABEL = {
    "info": "Инфо (звук/радар)",
    "timing": "Тайминг",
    "position": "Позиция",
    "discipline": "Дисциплина",
    "mechanics": "Механика",
}


def update_history(profile: Dict, cause: str) -> None:
    history = profile.setdefault("cause_history", [])
    history.append(cause)
    if len(history) > 12:
        profile["cause_history"] = history[-12:]


def detect_pattern(profile: Dict) -> Optional[str]:
    history: List[str] = profile.get("cause_history", [])
    if len(history) < MIN_REPEAT:
        return None

    last_ts = profile.get("last_pattern_ts", 0)
    if time.time() - last_ts < COOLDOWN:
        return None

    window = history[-WINDOW:]
    counter = Counter(window)
    top_cause, count = counter.most_common(1)[0]

    if count < MIN_REPEAT:
        return None

    lines = [
        "🧠 Наблюдение (паттерн)",
        f"За последние {len(window)} смертей:",
        f"• {count} — {CAUSE_LABEL.get(top_cause, top_cause)}",
        "",
    ]

    if top_cause == "position":
        lines.append("Ты репикаешь или стоишь на линии прострела.")
    elif top_cause == "timing":
        lines.append("Ты выходишь в предсказуемый момент.")
    elif top_cause == "info":
        lines.append("Ты играешь без подтверждённого инфо.")
    elif top_cause == "discipline":
        lines.append("Ты форсишь файт без ресета.")
    elif top_cause == "mechanics":
        lines.append("Это механика: контроль важнее скорости.")

    lines.append("")
    lines.append("🎯 Лечим привычку, не симптом.")

    profile["last_pattern_ts"] = time.time()
    return "\n".join(lines)
