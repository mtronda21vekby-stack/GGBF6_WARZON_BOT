# -*- coding: utf-8 -*-
from __future__ import annotations
import re
import random


DEMON_PHRASES_START = [
    "Соберись.",
    "Холодно.",
    "Без паники.",
    "Думай.",
    "Контроль.",
]

DEMON_PRESSURE = [
    "Ты умер не из-за зомби. Из-за решения.",
    "Слабая позиция = гарантированная смерть.",
    "Ты знал, что так будет.",
    "Ошибка была раньше remembering.",
    "Ты торопился. Карта — нет.",
]

DEMON_FINISH = [
    "Исправь и иди дальше.",
    "Следующая попытка — без этой ошибки.",
    "Контроль или выход.",
]


def parse_player_input(text: str) -> dict:
    """
    Формат:
    Карта: ashes | Раунд: 22 | Умираю от: узко | Есть: PAP, Jug | Режим: demon
    """
    result = {
        "map": None,
        "round": None,
        "death": None,
        "have": [],
        "mode": "normal",
    }

    if not text:
        return result

    m = re.search(r"карта\s*:\s*(\w+)", text, re.IGNORECASE)
    if m:
        result["map"] = m.group(1).lower()

    m = re.search(r"раунд\s*:\s*(\d+)", text, re.IGNORECASE)
    if m:
        result["round"] = int(m.group(1))

    m = re.search(r"умираю\s*от\s*:\s*([^\|]+)", text, re.IGNORECASE)
    if m:
        result["death"] = m.group(1).strip().lower()

    m = re.search(r"есть\s*:\s*(.+)", text, re.IGNORECASE)
    if m:
        result["have"] = [x.strip().lower() for x in m.group(1).split(",")]

    m = re.search(r"режим\s*:\s*(\w+)", text, re.IGNORECASE)
    if m:
        result["mode"] = m.group(1).lower()

    return result


def zombie_coach_reply(p: dict) -> str:
    mode = p.get("mode", "normal")
    map_ = p.get("map")
    round_ = p.get("round")
    death = p.get("death") or ""
    have = p.get("have") or []

    demon = mode == "demon"

    # ---------- CORE ACTION ----------
    if "узко" in death:
        action = "ВЫХОД. НЕ СТРЕЛЯЙ. ШАГ В СТОРОНУ."
    elif "толпа" in death:
        action = "СОБЕРИ ОРДУ. УБИВАЙ В ПРОСТОРЕ."
    elif "спец" in death:
        action = "УБЕРИ МЕЛОЧЬ. НАКАЗЫВАЙ В ОТКАТЕ."
    else:
        action = "ДИСТАНЦИЯ. ВЫХОДЫ. ПЕРЕЗАРЯДКА."

    # ---------- NEXT STEP ----------
    if round_ is not None:
        if round_ <= 10:
            nxt = "ПРОСТОР. МАРШРУТ. МИНИМУМ ПОКУПОК."
        elif round_ <= 25:
            nxt = "СТАБИЛЬНЫЙ КРУГ. 1 PAP. ВТОРОЙ ВЫХОД."
        else:
            nxt = "КОНТРОЛЬ. МЕДЛЕННО. БЕЗ РИСКА."
    else:
        nxt = "СТАБИЛИЗИРУЙ ПОЗИЦИЮ."

    # ---------- MAP PRESSURE ----------
    map_block = ""
    if map_ == "ashes":
        map_block = "ASHES: МЕНЯЙ ПОЗИЦИЮ РАНЬШЕ, ЧЕМ ХОЧЕТСЬ."
    elif map_ == "astra":
        map_block = "ASTRA: EE ПОСЛЕ СТАБИЛИЗАЦИИ. НЕ СПЕШИ."

    # ---------- ERROR ----------
    if "pap" in have and "узко" in death:
        err = "УРОН БЕЗ ПОЗИЦИИ = ТРУП."
    elif "jug" in have and "толпа" in death:
        err = "HP НЕ ЛЕЧИТ ПЛОХИЕ РЕШЕНИЯ."
    else:
        err = "НЕТ ПЛАНА ОТХОДА."

    # ---------- DEMON STYLE ----------
    if demon:
        lines = [
            random.choice(DEMON_PHRASES_START),
            action,
            nxt,
        ]

        if map_block:
            lines.append(map_block)

        lines.append(random.choice(DEMON_PRESSURE))
        lines.append(err)
        lines.append(random.choice(DEMON_FINISH))

        return "\n".join(lines)

    # ---------- NORMAL / PRO ----------
    return "\n\n".join([
        "🚑 СЕЙЧАС:\n• " + action.replace(". ", "\n• "),
        "➡️ ДАЛЬШЕ:\n• " + nxt.replace(". ", "\n• "),
        ("🗺 КАРТА:\n• " + map_block) if map_block else "",
        "❌ ОШИБКА:\n• " + err,
    ]).strip()
