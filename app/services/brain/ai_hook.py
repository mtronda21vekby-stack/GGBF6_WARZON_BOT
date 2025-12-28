# app/services/brain/ai_hook.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import httpx

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


def _difficulty_style(diff: str) -> str:
    d = (diff or "Normal").lower()
    if "demon" in d:
        return "очень жёстко, коротко, ультра-практично, без воды"
    if "pro" in d:
        return "строго, по делу, как капитан/коуч"
    return "дружелюбно и понятно, но всё равно по делу"


@dataclass
class AIHook:
    api_key: str
    model: str = "gpt-4.1-mini"

    def generate(self, *, profile: Dict[str, Any], history: List[dict], user_text: str) -> str:
        if OpenAI is None:
            return "ИИ: ERROR\nopenai package not installed. Добавь в requirements: openai>=1.40.0"

        style = _difficulty_style(str(profile.get("difficulty", "Normal")))
        game = profile.get("game", "Warzone")
        platform = profile.get("platform", "PC")
        inp = profile.get("input", "Controller")
        bf6_class = profile.get("bf6_class", "Assault")

        system = (
            "Ты — FPS coach и тиммейт топ уровня.\n"
            f"Стиль ответа: {style}.\n"
            "Формат: 1) Диагноз 2) СЕЙЧАС (3 пункта) 3) ДАЛЬШЕ (3 пункта) 4) Тренировка (2 упражнения).\n"
            "Если не хватает данных — задай 2 коротких вопроса в конце, не больше.\n"
            "Не пиши общие советы, всегда привязывай к ситуации.\n\n"
            f"Профиль игрока:\n"
            f"- game: {game}\n- platform: {platform}\n- input: {inp}\n- bf6_class: {bf6_class}\n"
        )

        msgs: List[dict] = [{"role": "system", "content": system}]

        # ограничим историю, но НЕ режем функционал
        tail = (history or [])[-12:]
        for m in tail:
            r = m.get("role")
            c = m.get("content")
            if r in ("user", "assistant") and c:
                msgs.append({"role": r, "content": str(c)})

        msgs.append({"role": "user", "content": user_text})

        try:
            client = OpenAI(api_key=self.api_key, timeout=30)
            resp = client.chat.completions.create(
                model=self.model,
                messages=msgs,
                temperature=0.7,
            )
            return resp.choices[0].message.content.strip()
        except httpx.ConnectError as e:
            return (
                "ИИ: ERROR\nAPIConnectionError: Connection error.\n\n"
                "Проверь в Render:\n"
                "• OPENAI_API_KEY (валидный)\n"
                "• AI_ENABLED=1\n"
                "• outbound network не блокируется\n"
                f"\nДетали: {e}"
            )
        except Exception as e:
            return f"ИИ: ERROR\n{type(e).__name__}: {e}"
