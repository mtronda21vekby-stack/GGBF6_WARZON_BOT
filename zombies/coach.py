# -*- coding: utf-8 -*-
from __future__ import annotations

import re


def parse_player_input(text: str) -> dict:
    """
    Парсим строку вида:
    Раунд: 18 | Умираю от: узко | Есть: PAP, Jug
    """
    result = {
        "round": None,
        "death": None,
        "have": [],
    }

    if not text:
        return result

    # Раунд
    m = re.search(r"раунд\s*:\s*(\d+)", text, re.IGNORECASE)
    if m:
        result["round"] = int(m.group(1))

    # Причина смерти
    m = re.search(r"умираю\s*от\s*:\s*([^\|]+)", text, re.IGNORECASE)
    if m:
        result["death"] = m.group(1).strip().lower()

    # Что есть
    m = re.search(r"есть\s*:\s*(.+)", text, re.IGNORECASE)
    if m:
        items = m.group(1)
        result["have"] = [i.strip().lower() for i in items.split(",")]

    return result


def zombie_coach_reply(parsed: dict) -> str:
    """
    Формирует ответ:
    Сейчас / Дальше / Главная ошибка
    """
    round_ = parsed.get("round")
    death = parsed.get("death") or ""
    have = parsed.get("have") or []

    parts = []

    # --- СЕЙЧАС ---
    if "узко" in death:
        now = (
            "СЕЙЧАС:\n"
            "• НЕ стреляй — освободи выход\n"
            "• Резкий шаг в сторону, не назад\n"
            "• Убери ближайших, а не дальних"
        )
    elif "толпа" in death:
        now = (
            "СЕЙЧАС:\n"
            "• Прекрати фармить очки\n"
            "• Собери орду в один хвост\n"
            "• Только потом убивай"
        )
    elif "спец" in death:
        now = (
            "СЕЙЧАС:\n"
            "• Очисти мелочь вокруг\n"
            "• Вынуди спец-зомби атаковать\n"
            "• Накажи в откате"
        )
    else:
        now = (
            "СЕЙЧАС:\n"
            "• Сохрани дистанцию\n"
            "• Проверь выходы\n"
            "• Перезарядись в просторе"
        )

    parts.append(now)

    # --- ДАЛЬШЕ ---
    if round_ is not None:
        if round_ <= 10:
            next_ = (
                "ДАЛЬШЕ:\n"
                "• Открой пространство\n"
                "• Учишь маршрут\n"
                "• Минимум покупок"
            )
        elif round_ <= 25:
            next_ = (
                "ДАЛЬШЕ:\n"
                "• Стабильный круг\n"
                "• 1 улучшенное оружие\n"
                "• Запасной выход"
            )
        else:
            next_ = (
                "ДАЛЬШЕ:\n"
                "• Контроль важнее урона\n"
                "• Минимум риска\n"
                "• Терпение"
            )
        parts.append(next_)

    # --- ГЛАВНАЯ ОШИБКА ---
    if "pap" in have and "узко" in death:
        mistake = (
            "ГЛАВНАЯ ОШИБКА:\n"
            "• Урон есть, а позиции нет\n"
            "• Ты вложился в пушку раньше простора"
        )
    elif "jug" in have and "толпа" in death:
        mistake = (
            "ГЛАВНАЯ ОШИБКА:\n"
            "• Надеешься на хп\n"
            "• Jug не спасает от плохой позиции"
        )
    else:
        mistake = (
            "ГЛАВНАЯ ОШИБКА:\n"
            "• Отсутствие плана отхода"
        )

    parts.append(mistake)

    return "\n\n".join(parts)
