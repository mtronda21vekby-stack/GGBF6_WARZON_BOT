# zombies/router.py
# -*- coding: utf-8 -*-

from typing import Dict, Any, Optional
from zombies.registry import load_maps, get_map

def zombies_menu():
    rows = []
    maps = load_maps()
    for m in maps:
        rows.append([{"text": f"🗺 {m.MAP_NAME}", "callback_data": f"zmb:map:{m.MAP_ID}"}])
    rows.append([{"text": "⬅️ Back", "callback_data": "nav:main"}])
    return {"inline_keyboard": rows}

def map_sections_menu(map_id: str):
    m = get_map(map_id)
    if not m:
        return {"inline_keyboard": [[{"text": "⬅️ Back", "callback_data": "zmb:home"}]]}
    rows = []
    for sid, title in m.list_buttons():
        rows.append([{"text": title, "callback_data": f"zmb:sec:{map_id}:{sid}"}])
    rows.append([{"text": "⬅️ Back to maps", "callback_data": "zmb:home"}])
    return {"inline_keyboard": rows}

def handle_callback(data: str) -> Optional[Dict[str, Any]]:
    """
    Возвращает:
      { "text": "...", "reply_markup": {...} }
    Или None если это НЕ zombies callback.
    """
    if not data.startswith("zmb:"):
        return None

    if data == "zmb:home":
        return {"text": "🧟 Zombies — выбери карту:", "reply_markup": zombies_menu()}

    if data.startswith("zmb:map:"):
        map_id = data.split(":", 2)[2]
        m = get_map(map_id)
        if not m:
            return {"text": "Карта не найдена 😅", "reply_markup": zombies_menu()}
        return {"text": f"🗺 {m.MAP_NAME}\nВыбери раздел:", "reply_markup": map_sections_menu(map_id)}

    if data.startswith("zmb:sec:"):
        parts = data.split(":", 3)
        if len(parts) != 4:
            return {"text": "Ошибка секции 😅", "reply_markup": zombies_menu()}

        map_id, section_id = parts[2], parts[3]
        m = get_map(map_id)
        if not m:
            return {"text": "Карта не найдена 😅", "reply_markup": zombies_menu()}

        sec = m.get_section(section_id)
        if not sec:
            return {"text": "Раздел не найден 😅", "reply_markup": map_sections_menu(map_id)}

        return {"text": sec["text"], "reply_markup": map_sections_menu(map_id)}

    return {"text": "🧟 Zombies — выбери карту:", "reply_markup": zombies_menu()}
