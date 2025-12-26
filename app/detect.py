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