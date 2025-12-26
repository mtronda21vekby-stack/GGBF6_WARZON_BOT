# -*- coding: utf-8 -*-
from typing import Dict, Any, Optional, List

from zombies import ashes_of_damned, astra_malorum


MAPS = {
    ashes_of_damned.MAP_ID: ashes_of_damned,
    astra_malorum.MAP_ID: astra_malorum,
}

DEFAULT_MAP_ID = ashes_of_damned.MAP_ID


def _safe_map_id(map_id: str) -> str:
    return map_id if map_id in MAPS else DEFAULT_MAP_ID


def _map_name(map_id: str) -> str:
    m = MAPS.get(map_id)
    return getattr(m, "MAP_NAME", map_id)


def _menu_kb_buttons(map_id: str) -> Dict[str, Any]:
    map_id = _safe_map_id(map_id)
    m = MAPS[map_id]

    btns = m.list_buttons()  # [(id,title), ...]
    rows: List[List[Dict[str, str]]] = []

    for sid, title in btns:
        # sid должен быть строкой
        if not sid or sid == "intro":
            continue
        rows.append([{"text": title, "callback_data": f"zmb:sec:{map_id}:{sid}"}])

    rows.append([{"text": "🗺 Карты", "callback_data": "zmb:maps"}])
    rows.append([{"text": "⬅️ Назад", "callback_data": "nav:main"}])

    top = [[
        {"text": "🔎 Поиск", "callback_data": f"zmb:search:{map_id}"},
        {"text": "✅ Чек-лист", "callback_data": f"zmb:quick:{map_id}:checklist"},
    ]]

    return {"inline_keyboard": top + rows}


def _maps_kb() -> Dict[str, Any]:
    return {"inline_keyboard": [
        [{"text": f"🧟 {ashes_of_damned.MAP_NAME}", "callback_data": f"zmb:set:{ashes_of_damned.MAP_ID}"}],
        [{"text": f"🧟 {astra_malorum.MAP_NAME}", "callback_data": f"zmb:set:{astra_malorum.MAP_ID}"}],
        [{"text": "⬅️ Назад", "callback_data": "zmb:home"}],
    ]}


def _text_home(map_id: str) -> str:
    map_id = _safe_map_id(map_id)
    return (
        f"🔎 Поиск по карте: {_map_name(map_id)}\n\n"
        "Просто напиши слово/фразу, например:\n"
        "• чеклист\n• перки\n• спец\n• деньги\n• круг\n• ошибки\n"
    )


def handle_callback(data: str) -> Optional[Dict[str, Any]]:
    if not (data or "").startswith("zmb:"):
        return None

    parts = data.split(":")

    # zmb:home
    if data == "zmb:home":
        map_id = DEFAULT_MAP_ID
        intro = MAPS[map_id].get_section("intro") or {"text": "Zombies"}
        return {
            "text": _text_home(map_id) + "\n" + (intro.get("text") or ""),
            "reply_markup": _menu_kb_buttons(map_id),
            "set_profile": {"page": "zombies", "zmb_map": map_id},
        }

    # zmb:maps
    if data == "zmb:maps":
        return {"text": "🗺 Выбери карту:", "reply_markup": _maps_kb()}

    # zmb:set:<map_id>
    if len(parts) == 3 and parts[1] == "set":
        map_id = _safe_map_id(parts[2])
        intro = MAPS[map_id].get_section("intro") or {"text": "Zombies"}
        return {
            "text": _text_home(map_id) + "\n" + (intro.get("text") or ""),
            "reply_markup": _menu_kb_buttons(map_id),
            "set_profile": {"page": "zombies", "zmb_map": map_id},
        }

    # zmb:sec:<map_id>:<section_id>
    if len(parts) == 4 and parts[1] == "sec":
        map_id, sec_id = _safe_map_id(parts[2]), parts[3]
        sec = MAPS[map_id].get_section(sec_id)
        if not sec:
            sec = MAPS[map_id].get_section("intro") or {"text": "Раздел не найден."}
        return {"text": sec.get("text") or "—", "reply_markup": _menu_kb_buttons(map_id)}

    # zmb:search:<map_id>
    if len(parts) == 3 and parts[1] == "search":
        map_id = _safe_map_id(parts[2])
        return {"text": _text_home(map_id), "reply_markup": _menu_kb_buttons(map_id)}

    # zmb:quick:<map_id>:<what>
    if len(parts) == 4 and parts[1] == "quick":
        map_id, what = _safe_map_id(parts[2]), parts[3]
        sec = MAPS[map_id].get_section(what) or MAPS[map_id].get_section("intro") or {"text": "—"}
        return {"text": sec.get("text") or "—", "reply_markup": _menu_kb_buttons(map_id)}

    return {"text": "Zombies: не понял кнопку.", "reply_markup": _maps_kb()}


def handle_text(query: str, current_map: str) -> Optional[Dict[str, Any]]:
    map_id = _safe_map_id(current_map)
    mod = MAPS[map_id]

    q = (query or "").strip()
    if not q:
        return {"text": _text_home(map_id), "reply_markup": _menu_kb_buttons(map_id)}

    search_fn = getattr(mod, "search_sections", None)
    if callable(search_fn):
        hits = search_fn(q) or []
    else:
        hits = []
        for s in getattr(mod, "SECTIONS", []) or []:
            if not isinstance(s, dict):
                continue
            blob = (
                (s.get("title", "") + " " + s.get("text", "") + " " + " ".join(s.get("keywords") or []))
                .lower()
            )
            if q.lower() in blob:
                hits.append(s)

    if not hits:
        return {
            "text": f"❌ Не нашёл по запросу: «{q}»\n\nПопробуй: чеклист / перки / босс / квест / ловушки / деньги",
            "reply_markup": _menu_kb_buttons(map_id),
        }

    if len(hits) == 1:
        return {"text": (hits[0].get("text") or "—"), "reply_markup": _menu_kb_buttons(map_id)}

    rows: List[List[Dict[str, str]]] = []
    for s in hits[:10]:
        sid = s.get("id") or ""
        title = s.get("title") or "Раздел"
        if not sid:
            # если id нет — даём просмотр без перехода, чтобы не было битых кнопок
            rows.append([{"text": title, "callback_data": f"zmb:search:{map_id}"}])
            continue
        rows.append([{"text": title, "callback_data": f"zmb:sec:{map_id}:{sid}"}])

    rows.append([{"text": "⬅️ Назад", "callback_data": "zmb:home"}])

    return {
        "text": f"🔎 Нашёл {len(hits)} совпадений по «{q}». Выбери раздел:",
        "reply_markup": {"inline_keyboard": rows},
    }
