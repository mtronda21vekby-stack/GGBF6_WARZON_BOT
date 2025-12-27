# -*- coding: utf-8 -*-
from typing import Dict, Any

GAMES = ("warzone", "bf6", "bo7")

GAME_TITLES: Dict[str, str] = {
    "warzone": "Warzone",
    "bf6": "BF6",
    "bo7": "BO7",
}

def game_title(game: str) -> str:
    return GAME_TITLES.get(game, game or "AUTO")

def resolve_game(chat_id: int, user_text: str) -> str:
    # берём из профиля если зафиксировано, иначе авто-дефолт
    from app.state import ensure_profile
    p = ensure_profile(chat_id)
    forced = p.get("game", "auto")
    if forced in GAMES:
        return forced

    t = (user_text or "").lower()
    if "bf" in t or "battlefield" in t:
        return "bf6"
    if "bo7" in t or "black ops" in t:
        return "bo7"
    return "warzone"