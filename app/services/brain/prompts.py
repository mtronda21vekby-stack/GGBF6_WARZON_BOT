# -*- coding: utf-8 -*-
from __future__ import annotations


def build_ai_messages(
    game: str,
    mode: str,
    role: str | None,
    platform: str | None,
    input_: str | None,
    world_settings: dict | None,
    user_text: str,
    memory_hint: str | None = None,
) -> list[dict]:
    g = (game or "warzone").lower()
    m = (mode or "normal").lower()
    r = (role or "none").lower()

    # Требование: BF6 — labels EN; остальное — RU.
    ru = g in ("warzone", "bo7", "zombies")

    persona = {
        "normal": "Calm coach teammate. Clear, supportive, short.",
        "pro": "Pro FPS coach. Direct, structured, tactical.",
        "demon": "Demon-tier teammate coach. Brutally honest, high standards, no fluff.",
    }.get(m, "Calm coach teammate.")

    if ru:
        system = (
            "Ты — ультра-премиум FPS коуч-тиммейт. "
            "Отвечай СТРУКТУРНО, без воды. "
            "Дай: 1) Причина 2) Что делать сейчас 3) Что делать дальше 4) Мини-тренировка 10 минут. "
            "Учти мир игры, режим мышления и роль."
        )
    else:
        system = (
            "You are an ultra-premium FPS coach teammate. "
            "Be STRUCTURED, no fluff. "
            "Give: 1) Root cause 2) What to do now 3) What to do next 4) 10-min micro-drill. "
            "Respect game world, mindset mode, and role."
        )

    ctx = {
        "game": g,
        "mode": m,
        "role": r,
        "platform": (platform or "unknown"),
        "input": (input_ or "unknown"),
        "settings": (world_settings or {}),
        "memory_hint": (memory_hint or ""),
        "user_text": user_text,
    }

    if ru:
        user = (
            "КОНТЕКСТ:\n"
            f"- Игра: {ctx['game']}\n"
            f"- Режим: {ctx['mode']}\n"
            f"- Роль: {ctx['role']}\n"
            f"- Платформа: {ctx['platform']}\n"
            f"- Input: {ctx['input']}\n"
            f"- Настройки: {ctx['settings']}\n"
            f"- Повторяющаяся ошибка (если есть): {ctx['memory_hint']}\n\n"
            "СИТУАЦИЯ ИГРОКА:\n"
            f"{ctx['user_text']}\n"
        )
    else:
        user = (
            "CONTEXT:\n"
            f"- Game: {ctx['game']}\n"
            f"- Mode: {ctx['mode']}\n"
            f"- Role: {ctx['role']}\n"
            f"- Platform: {ctx['platform']}\n"
            f"- Input: {ctx['input']}\n"
            f"- Settings: {ctx['settings']}\n"
            f"- Repeating mistake (if any): {ctx['memory_hint']}\n\n"
            "PLAYER SITUATION:\n"
            f"{ctx['user_text']}\n"
        )

    return [
        {"role": "system", "content": system},
        {"role": "system", "content": f"Persona: {persona}"},
        {"role": "user", "content": user},
    ]
