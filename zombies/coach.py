# -*- coding: utf-8 -*-
from __future__ import annotations
import re


def parse_player_input(text: str) -> dict:
    """
    Формат:
    Карта: ashes | Раунд: 18 | Умираю от: узко | Есть: PAP, Jug | Режим: demon
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

    # -------- СЕЙЧАС --------
    if "узко" in death:
        now = "ВЫХОД. НЕ СТРЕЛЯЙ. ШАГ В СТОРОНУ."
    elif "толпа" in death:
        now = "СОБЕРИ ОРДУ. УБИВАЙ ТОЛЬКО В ПРОСТОРЕ."
    elif "спец" in death:
        now = "УБЕРИ МЕЛОЧЬ. НАКАЗЫВАЙ В ОТКАТЕ."
    else:
        now = "ДИСТАНЦИЯ. ВЫХОДЫ. ПЕРЕЗАРЯДКА."

    if not demon:
        now = "🚑 СЕЙЧАС:\n• " + now.replace(". ", "\n• ")

    # -------- ДАЛЬШЕ --------
    if round_ is not None:
        if round_ <= 10:
            nxt = "ОТКРЫВАЙ ПРОСТОР. УЧИ МАРШРУТ."
        elif round_ <= 25:
            nxt = "СТАБИЛЬНЫЙ КРУГ. 1 PAP. ЗАПАСНОЙ ВЫХОД."
        else:
            nxt = "КОНТРОЛЬ. МИНИМУМ РИСКА. ТЕРПЕНИЕ."
    else:
        nxt = "СТАБИЛИЗИРУЙ ПОЗИЦИЮ."

    if not demon:
        nxt = "➡️ ДАЛЬШЕ:\n• " + nxt.replace(". ", "\n• ")

    # -------- КАРТА --------
    map_tip = ""
    if map_ == "ashes":
        map_tip = (
            "ASHES:\n"
            "• Не задерживайся в узких секциях\n"
            "• Меняй позицию раньше, чем кажется нужным"
        )
    elif map_ == "astra":
        map_tip = (
            "ASTRA:\n"
            "• EE только после стабилизации\n"
            "• Босс наказывает спешку"
        )

    if demon and map_tip:
        map_tip = "КАРТА:\n" + map_tip.replace(":\n", " — ")

    # -------- ОШИБКА --------
    if "pap" in have and "узко" in death:
        err = "УРОН БЕЗ ПОЗИЦИИ = СМЕРТЬ."
    elif "jug" in have and "толпа" in death:
        err = "HP НЕ СПАСАЕТ ОТ ПАНИКИ."
    else:
        err = "НЕТ ПЛАНА ОТХОДА."

    if not demon:
        err = "❌ ОШИБКА:\n• " + err

    # -------- СБОРКА --------
    blocks = [now, nxt]
    if map_tip:
        blocks.append(map_tip)
    blocks.append(err)

    return "\n\n".join(blocks)
