# -*- coding: utf-8 -*-
"""
Pattern Engine
Анализирует повторы ошибок и привычки игрока.
НЕ отвечает всегда — только когда есть смысл.
"""

from typing import Dict, List, Optional
from collections import Counter
import time

# сколько последних событий анализируем
WINDOW = 8

# минимальное число повторов, чтобы считать паттерном
MIN_REPEAT = 3

CAUSE_LABEL = {
    "info": "Инфо (звук/радар)",
    "timing": "Тайминг",
    "position": "Позиция",
    "discipline": "Дисциплина",
    "mechanics": "Механика",
}


def detect_pattern(
    stats: Dict[str, int],
    recent_causes: List[str],
    last_ts: float,
) -> Optional[str]:
    """
    Возвращает текст наблюдения ИЛИ None
    """

    if not recent_causes or len(recent_causes) < MIN_REPEAT:
        return None

    # анализ окна
    window = recent_causes[-WINDOW:]
    c = Counter(window)

    top_cause, count = c.most_common(1)[0]
    if count < MIN_REPEAT:
        return None

    label = CAUSE_LABEL.get(top_cause, top_cause)

    # простая анти-спам защита (не чаще раза в 3 минуты)
    if time.time() - last_ts < 180:
        return None

    lines = [
        "🧠 **Наблюдение (паттерн)**",
        f"За последние {len(window)} смертей:",
        f"• {count} — {label}",
        "",
    ]

    # микро-выводы
    if top_cause == "position":
        lines.append("Ты **репикаешь или стоишь на линии прострела**.")
    elif top_cause == "timing":
        lines.append("Ты **выходишь в предсказуемый момент**.")
    elif top_cause == "info":
        lines.append("Ты **играешь без подтверждённого инфо**.")
    elif top_cause == "discipline":
        lines.append("Ты **форсишь файт без ресета**.")
    elif top_cause == "mechanics":
        lines.append("Это **механика**, но не сенса — скорее контроль.")

    lines += [
        "",
        "🎯 **Лечим привычку, не симптом.**",
    ]

    return "\n".join(lines)
