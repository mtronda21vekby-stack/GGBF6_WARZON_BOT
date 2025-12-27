# -*- coding: utf-8 -*-
from typing import Dict, Any, List

from app.state import ensure_profile, get_memory

PERSONA_PROMPTS = {
    "spicy": "Ты дерзкий, мотивирующий FPS-коуч. Коротко, уверенно, по делу. Иногда эмодзи.",
    "chill": "Ты спокойный и дружелюбный FPS-коуч. Объясняешь мягко и понятно.",
    "pro":   "Ты строгий тренер-про. Структурируешь, даёшь drills, ошибки, исправления.",
}

VERBOSITY_HINT = {
    "short": "Отвечай очень коротко: 3-6 строк максимум.",
    "normal": "Отвечай умеренно: 8-14 строк максимум.",
    "talkative": "Можно подробно, но без воды. Структура обязательна.",
}

MODE_HINT = {
    "chat": "Режим: диалог. Можно задавать уточняющие вопросы и давать советы.",
    "coach": "Режим: тренер. Всегда даёшь план: Ошибка → Почему → Исправление → Дрилл.",
}

LEVEL_HINT = {
    "normal": "Уровень игрока: обычный. Больше базовых советов.",
    "pro": "Уровень игрока: продвинутый. Больше микро-моментов и таймингов.",
    "demon": "Уровень игрока: демон. Жёсткая аналитика, тонкие фишки, high-skill советы.",
}

GAME_HINT = {
    "auto": "Игра: авто. Если пользователь пишет Warzone/BF6/BO7/Zombies — подстраивайся.",
    "warzone": "Игра: Warzone. Термины: rotate, timing, third-party, loadout, gulag.",
    "bf6": "Игра: BF6. Термины: recoil control, movement, positioning, objective.",
    "bo7": "Игра: BO7. Термины: spawns, lanes, pre-aim, centering, map control.",
}

class BrainV3:
    def __init__(self, *, ai_engine, log, cfg):
        self.ai = ai_engine
        self.log = log
        self.cfg = cfg

    def build_system(self, profile: Dict[str, Any]) -> str:
        persona = profile.get("persona", "spicy")
        verbosity = profile.get("verbosity", "normal")
        mode = profile.get("mode", "chat")
        level = profile.get("player_level", "demon")
        game = profile.get("game", "auto")

        parts = [
            "Ты Brain v3 — премиум FPS AI ассистент (Warzone/BF6/BO7/Zombies).",
            PERSONA_PROMPTS.get(persona, PERSONA_PROMPTS["spicy"]),
            VERBOSITY_HINT.get(verbosity, VERBOSITY_HINT["normal"]),
            MODE_HINT.get(mode, MODE_HINT["chat"]),
            LEVEL_HINT.get(level, LEVEL_HINT["demon"]),
            GAME_HINT.get(game, GAME_HINT["auto"]),
            "Пиши по-русски. Всегда давай конкретику (позиция, угол, тайминг, дрилл).",
        ]
        return "\n".join(parts)

    def reply(self, chat_id: int, user_text: str) -> str:
        p = ensure_profile(chat_id)
        system = self.build_system(p)

        mem = get_memory(chat_id)
        messages: List[Dict[str, str]] = []
        # память (если включена)
        for m in mem[-(self.cfg.MEMORY_MAX_TURNS * 2):]:
            role = m.get("role", "user")
            content = m.get("content", "")
            if content:
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": user_text})

        return self.ai.reply(system=system, messages=messages)