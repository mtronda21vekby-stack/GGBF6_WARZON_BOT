# zombies/router.py
# -*- coding: utf-8 -*-
from typing import Dict, Any, Optional, List, Tuple

from zombies import ashes_of_damned as ashes
from zombies import astra_malorum as ritual


# Карты, которые доступны
MAPS = {
    ashes.MAP_ID: ashes,
    ritual.MAP_ID: ritual,
}

# Красивые названия
MAP_TITLES = [
    (ashes.MAP_ID, ashes.MAP_NAME),
    (ritual.MAP_ID, ritual.MAP_NAME),
]


def _kb_home():
    return {
        "inline_keyboard": [
            [{"text": f"🧟 {name}", "callback_data": f"zmb:map:{mid}"}] for mid, name in MAP_TITLES
        ] + [
            [{"text": "⬅️ Назад", "callback_data": "nav:main"}],
        ]
    }


def _kb_map(map_id: str):
    mod = MAPS.get(map_id)
    rows = []
    rows.append([
        {"text": "🔎 Поиск", "callback_data": f"zmb:search:{map_id}"},
        {"text": "✅ Чек-лист", "callback_data": f"zmb:sec:{map_id}:checklist"},
    ])
    for sec_id, title in mod.list_buttons():
        rows.append([{"text": title, "callback_data": f"zmb:sec:{map_id}:{sec_id}"}])
    rows.append([{"text": "⬅️ Карты", "callback_data": "zmb:home"}])
    rows.append([{"text": "⬅️ Назад", "callback_data": "nav:main"}])
    return {"inline_keyboard": rows}


def _module(map_id: str):
    return MAPS.get(map_id) or ashes


def handle_callback(data: str) -> Optional[Dict[str, Any]]:
    """
    Возвращает dict:
      { "text": "...", "reply_markup": {...}, "set_profile": {...} }
    либо None, если это не zombies callback.
    """
    data = (data or "").strip()
    if not data.startswith("zmb:"):
        return None

    # Главная: выбор карты
    if data == "zmb:home":
        return {
            "text": "🧟 Zombies — выбери карту:",
            "reply_markup": _kb_home(),
            "set_profile": {"page": "zombies"},
        }

    # Выбрали карту
    if data.startswith("zmb:map:"):
        map_id = data.split(":", 2)[2]
        mod = _module(map_id)
        return {
            "text": f"🧟 {mod.MAP_NAME}\n\nВыбери раздел или жми «🔎 Поиск».",
            "reply_markup": _kb_map(mod.MAP_ID),
            "set_profile": {"page": "zombies", "zmb_map": mod.MAP_ID},
        }

    # Подсказка поиска
    if data.startswith("zmb:search:"):
        map_id = data.split(":", 2)[2]
        mod = _module(map_id)
        return {
            "text": (
                f"🔎 Поиск по карте: {mod.MAP_NAME}\n\n"
                "Просто напиши слово/фразу, например:\n"
                "• чеклист\n• перки\n• спец\n• деньги\n• круг\n• ошибки\n"
            ),
            "reply_markup": _kb_map(mod.MAP_ID),
            "set_profile": {"page": "zombies", "zmb_map": mod.MAP_ID},
        }

    # Открыть раздел
    if data.startswith("zmb:sec:"):
        parts = data.split(":")
        if len(parts) < 4:
            return {"text": "Раздел не найден 😅", "reply_markup": _kb_home(), "set_profile": {"page": "zombies"}}

        map_id = parts[2]
        sec_id = parts[3]
        mod = _module(map_id)

        sec = mod.get_section(sec_id)
        if not sec:
            return {
                "text": "Раздел не найден 😅",
                "reply_markup": _kb_map(mod.MAP_ID),
                "set_profile": {"page": "zombies", "zmb_map": mod.MAP_ID},
            }

        return {
            "text": f"{sec['title']}\n\n{sec['text']}",
            "reply_markup": _kb_map(mod.MAP_ID),
            "set_profile": {"page": "zombies", "zmb_map": mod.MAP_ID},
        }

    # Фоллбек
    return {"text": "🧟 Zombies — выбери карту:", "reply_markup": _kb_home(), "set_profile": {"page": "zombies"}}


def handle_text(user_text: str, current_map: str) -> Optional[Dict[str, Any]]:
    """
    Если мы в режиме zombies (page=zombies), любое сообщение ищем по карте.
    Возвращаем ответ или None (если пусто).
    """
    q = (user_text or "").strip()
    if not q:
        return None

    mod = _module(current_map)

    # Прямые быстрые ключи (чтобы было супер-понятно)
    aliases = {
        "чек": "checklist",
        "чеклист": "checklist",
        "перки": "perks",
        "перк": "perks",
        "оружие": "weapons",
        "пушки": "weapons",
        "спец": "specials",
        "элит": "specials",
        "деньги": "economy",
        "эконом": "economy",
        "круг": "movement",
        "пози": "movement",
        "ошиб": "mistakes",
        "дальше": "stuck",
        "застрял": "stuck",
        "старт": "start",
    }
    low = q.lower()
    for k, sec_id in aliases.items():
        if k in low:
            sec = mod.get_section(sec_id)
            if sec:
                return {"text": f"{sec['title']}\n\n{sec['text']}", "reply_markup": _kb_map(mod.MAP_ID)}

    hits = mod.search_sections(q)
    if not hits:
        return {
            "text": (
                f"Ничего не нашёл по «{q}» 😅\n\n"
                "Попробуй: чеклист / перки / спец / деньги / круг / ошибки / старт"
            ),
            "reply_markup": _kb_map(mod.MAP_ID),
        }

    # если нашлось несколько — покажем 3 кнопки выбора
    top = hits[:3]
    rows = [[{"text": s["title"], "callback_data": f"zmb:sec:{mod.MAP_ID}:{s['id']}"}] for s in top]
    rows.append([{"text": "⬅️ Назад", "callback_data": f"zmb:map:{mod.MAP_ID}"}])

    return {
        "text": f"🔎 Нашёл по «{q}». Выбери что открыть:",
        "reply_markup": {"inline_keyboard": rows},
    }
