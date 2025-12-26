# -*- coding: utf-8 -*-
import re
from typing import Optional

_SMALLTALK_RX = re.compile(r"^\s*(привет|здаров|здравствуйте|йо|ку|qq|hello|hi|хай)\s*[!.\-–—]*\s*$", re.I)
_TILT_RX = re.compile(r"(я\s+говно|я\s+дно|не\s+прёт|не\s+идёт|вечно\s+не\s+везёт|тильт|бесит|ненавижу|заеб|сука|бля)", re.I)


def is_smalltalk(text: str) -> bool:
    return bool(_SMALLTALK_RX.match(text or ""))


def is_tilt(text: str) -> bool:
    return bool(_TILT_RX.search(text or ""))


def is_cheat_request(text: str) -> bool:
    t = (text or "").lower()
    banned = ["чит", "cheat", "hack", "обход", "античит", "exploit", "эксплойт", "аимбот", "wallhack", "вх", "спуфер"]
    return any(w in t for w in banned)


def detect_game(text: str) -> Optional[str]:
    t = (text or "").lower()
    if any(x in t for x in ["bf6", "battlefield", "батлфилд", "конквест", "захват"]):
        return "bf6"
    if any(x in t for x in ["bo7", "black ops", "блэк опс", "hardpoint", "хардпоинт", "zombies", "зомби"]):
        return "bo7"
    if any(x in t for x in ["warzone", "wz", "варзон", "verdansk", "rebirth", "gulag", "бр"]):
        return "warzone"
    return None


# =========================
# Root-cause classifier (для метрик/паттернов)
# =========================
CAUSES = ("info", "timing", "position", "discipline", "mechanics")

CAUSE_LABEL = {
    "info": "Инфо (звук/радар/пинги)",
    "timing": "Тайминг (когда пикнул/вышел)",
    "position": "Позиция (угол/высота/линия обзора)",
    "discipline": "Дисциплина (жадность/ресурсы/ресет)",
    "mechanics": "Механика (аим/отдача/сенса)",
}


def classify_cause(text: str) -> str:
    """
    Возвращает одну из причин:
    info | timing | position | discipline | mechanics
    """
    t = (text or "").lower()
    score = {c: 0 for c in CAUSES}

    # info
    for k in ["не слыш", "звук", "шаг", "радар", "пинг", "инфо", "увидел поздно", "не увидел", "не заметил"]:
        if k in t:
            score["info"] += 2

    # timing
    for k in ["тайм", "поздно", "рано", "репик", "репикнул", "пикнул", "вышел", "задержал", "перепушил", "пушнул"]:
        if k in t:
            score["timing"] += 2

    # position
    for k in ["пози", "угол", "высот", "открыт", "прострел", "линия", "укрыт", "пик с", "перекрест"]:
        if k in t:
            score["position"] += 2

    # discipline
    for k in ["жадн", "ресурс", "плейт", "пласти", "хил", "перезар", "ресет", "в соло", "вдвоём", "втроём", "погнал"]:
        if k in t:
            score["discipline"] += 2

    # mechanics
    for k in ["аим", "отдач", "сенс", "фов", "перел", "дрейф", "не попал", "мимо", "трек", "флик"]:
        if k in t:
            score["mechanics"] += 2

    best = max(score.items(), key=lambda kv: kv[1])[0]
    if score[best] == 0:
        return "position"
    return best
