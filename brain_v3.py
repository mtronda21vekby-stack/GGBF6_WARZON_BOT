# -*- coding: utf-8 -*-
"""
Brain v3 — FPS Coach Core
SAFE VERSION
- без UI
- без telegram
- без handlers
- можно импортировать куда угодно
"""

from typing import Dict, Any
import re

# =========================
# PLAYER TIERS
# =========================

PLAYER_TIERS = ("normal", "pro", "demon")

TIER_STYLE = {
    "normal": {
        "name": "Обычный игрок",
        "mindset": "учимся стабильности",
        "risk": "низкий",
    },
    "pro": {
        "name": "Профессионал",
        "mindset": "холодный расчёт",
        "risk": "контролируемый",
    },
    "demon": {
        "name": "Демон",
        "mindset": "максимальный прессинг и манс",
        "risk": "высокий",
    },
}

# =========================
# CAUSES (why died)
# =========================

CAUSES = (
    "info",
    "timing",
    "position",
    "mechanics",
    "discipline",
)

CAUSE_LABEL = {
    "info": "Недостаток информации",
    "timing": "Плохой тайминг",
    "position": "Позиционная ошибка",
    "mechanics": "Аим / механика",
    "discipline": "Жадность / отсутствие ресета",
}

CAUSE_KEYWORDS = {
    "info": ["не слыш", "звук", "шаг", "радар", "пинг"],
    "timing": ["рано", "поздно", "репик", "тайминг"],
    "position": ["угол", "пози", "открыт", "прострел"],
    "mechanics": ["аим", "отдач", "сенс", "не попал"],
    "discipline": ["жадн", "плейт", "ресет", "перезар"],
}

# =========================
# GAME PROFILES
# =========================

GAMES = ("warzone", "bf6", "bo7")

GAME_PROFILE = {
    "warzone": "Warzone",
    "bf6": "Battlefield 6",
    "bo7": "Black Ops",
}

# =========================
# CORE FUNCTIONS
# =========================

def classify_cause(text: str) -> str:
    text = (text or "").lower()
    score = {c: 0 for c in CAUSES}

    for cause, keys in CAUSE_KEYWORDS.items():
        for k in keys:
            if k in text:
                score[cause] += 1

    best = max(score, key=lambda k: score[k])
    return best if score[best] > 0 else "position"


def build_advice(game: str, cause: str, tier: str) -> str:
    tier = tier if tier in PLAYER_TIERS else "normal"

    if tier == "normal":
        return (
            f"🎯 Причина: {CAUSE_LABEL[cause]}\n"
            f"Что делать:\n"
            f"• Играй проще\n"
            f"• Сначала инфо, потом выход\n"
            f"• Не репикай тот же угол\n"
        )

    if tier == "pro":
        return (
            f"🎯 Причина: {CAUSE_LABEL[cause]}\n"
            f"Профессиональный подход:\n"
            f"• Контролируй дистанцию\n"
            f"• Репик только после инфо\n"
            f"• Планируй отход заранее\n"
        )

    # demon
    return (
        f"😈 ДЕМОН РЕЖИМ\n"
        f"Причина: {CAUSE_LABEL[cause]}\n"
        f"Тактика:\n"
        f"• Максимальный манс\n"
        f"• Фейк-пик → смена угла\n"
        f"• Дави после первого хита\n"
    )


def analyze_death(
    *,
    text: str,
    game: str = "warzone",
    tier: str = "normal",
) -> Dict[str, Any]:
    """
    Главная функция мозга
    """

    game = game if game in GAMES else "warzone"
    tier = tier if tier in PLAYER_TIERS else "normal"

    cause = classify_cause(text)

    advice = build_advice(game, cause, tier)

    return {
        "game": GAME_PROFILE[game],
        "tier": tier,
        "cause": cause,
        "cause_label": CAUSE_LABEL[cause],
        "advice": advice,
    }


# =========================
# QUICK TEST (safe)
# =========================

if __name__ == "__main__":
    demo = analyze_death(
        text="Не услышал шаги, репикнул тот же угол",
        game="bf6",
        tier="demon",
    )
    print(demo["advice"])
