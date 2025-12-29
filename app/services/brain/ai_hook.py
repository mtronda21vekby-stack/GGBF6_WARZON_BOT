# app/services/brain/ai_hook.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from openai import OpenAI


def _difficulty_style(diff: str) -> str:
    d = (diff or "Normal").lower()
    if "demon" in d:
        return "DEMON"
    if "pro" in d:
        return "PRO"
    return "NORMAL"


@dataclass
class AIHook:
    api_key: str
    model: str = "gpt-4.1-mini"

    def generate(self, *, profile: Dict[str, Any], history: List[dict], user_text: str) -> str:
        client = OpenAI(api_key=self.api_key)

        game = profile.get("game", "Warzone")
        platform = profile.get("platform", "PC")
        input_ = profile.get("input", "Controller")
        diff = profile.get("difficulty", "Normal")
        bf6_class = profile.get("bf6_class", "Assault")
        style = _difficulty_style(diff)

        system = f"""
Ты — ultra-premium FPS Coach. Отвечай как живой сильный тиммейт: коротко, по делу, но умно.
Стиль: {style}
Правила:
- Не отвечай шаблоном. Веди диалог.
- Всегда уточняй 1-2 вещи ТОЛЬКО если реально нужно, иначе сразу давай план.
- Формат ответа: 1) Диагноз (почему) 2) СЕЙЧАС (что делать прямо в бою) 3) ДАЛЬШЕ (тренировка/настройки)
- Учитывай текущий мир: game/platform/input и если BF6 — класс.
Контекст игрока:
- game={game}, platform={platform}, input={input_}, bf6_class={bf6_class}, difficulty={diff}
"""

        msgs = [{"role": "system", "content": system.strip()}]

        # добавим последние N из памяти
        for m in (history or [])[-20:]:
            role = m.get("role")
            content = m.get("content")
            if role in ("user", "assistant") and content:
                msgs.append({"role": role, "content": str(content)})

        msgs.append({"role": "user", "content": user_text})

        try:
            resp = client.chat.completions.create(
                model=self.model,
                messages=msgs,
                temperature=0.7 if style != "NORMAL" else 0.6,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            # важно: не молчать, а показать причину
            return (
                "🤖 ИИ: ERROR\n"
                f"{type(e).__name__}: {e}\n\n"
                "Проверь:\n"
                "• OPENAI_API_KEY\n"
                "• AI_ENABLED=1\n"
                "• requirements.txt: openai>=1.40.0\n"
                "• доступ Render к интернету (free иногда тупит)\n"
            )
