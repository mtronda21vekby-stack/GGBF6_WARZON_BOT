# -*- coding: utf-8 -*-
from typing import Optional, Dict, Any

from app.modules.warzone import WarzoneModule
from app.modules.bf6 import BF6Module
from app.modules.bo7 import BO7Module

WZ = WarzoneModule()
BF6 = BF6Module()
BO7 = BO7Module()

def by_key(key: str):
    key = (key or "").strip().lower()
    if key in ("wz", "warzone"):
        return WZ
    if key in ("bf6",):
        return BF6
    if key in ("bo7",):
        return BO7
    return None

def route_callback(data: str, chat_id: int) -> Optional[Dict[str, Any]]:
    # формат: mod:<game>:...
    if not (data or "").startswith("mod:"):
        return None
    parts = data.split(":")
    if len(parts) < 3:
        return None
    game = parts[1]
    m = by_key(game)
    if not m:
        return None
    return m.handle_callback(chat_id, data)

def route_text(chat_id: int, text: str, page: str) -> Optional[Dict[str, Any]]:
    # page: wz | bf6 | bo7
    m = by_key(page)
    if not m:
        return None
    return m.handle_text(chat_id, text)
