# app/services/brain/ai_hook.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List
import os
import time

import httpx
import certifi
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

    def _client(self) -> OpenAI:
        # Render иногда даёт сетевые глюки -> увеличиваем таймауты + ретраи
        timeout = httpx.Timeout(connect=15.0, read=60.0, write=30.0, pool=60.0)
        limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)

        http_client = httpx.Client(
            timeout=timeout,
            limits=limits,
            verify=certifi.where(),   # <-- важно для SSL на некоторых сборках
        )

        base_url = (os.getenv("OPENAI_BASE_URL", "") or "").strip() or None

        # OpenAI SDK 1.x умеет кастомный http_client
        return OpenAI(api_key=self.api_key, base_url=base_url, http_client=http_client)

    def generate(self, *, profile: Dict[str, Any], history: List[dict], user_text: str) -> str:
        client = self._client()

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
- Не отвечай шаблоном. Веди диалог. Не повторяй одну и ту же фразу.
- Если вводных мало — задай максимум 1-2 уточнения, иначе сразу давай план.
- Формат: 1) Диагноз 2) СЕЙЧАС (в бою) 3) ДАЛЬШЕ (тренировка/настройки)
Контекст игрока:
- game={game}, platform={platform}, input={input_}, bf6_class={bf6_class}, difficulty={diff}
""".strip()

        msgs = [{"role": "system", "content": system}]

        for m in (history or [])[-20:]:
            role = m.get("role")
            content = m.get("content")
            if role in ("user", "assistant") and content:
                msgs.append({"role": role, "content": str(content)})

        msgs.append({"role": "user", "content": user_text})

        # Ретраим 3 раза на сетевые фейлы
        last_err: Exception | None = None
        for attempt in range(1, 4):
            try:
                resp = client.chat.completions.create(
                    model=self.model,
                    messages=msgs,
                    temperature=0.65 if style == "NORMAL" else 0.75,
                )
                return (resp.choices[0].message.content or "").strip()
            except Exception as e:
                last_err = e
                time.sleep(0.6 * attempt)

        return (
            "🧠 ИИ: ERROR\n"
            f"{type(last_err).__name__}: {last_err}\n\n"
            "Что проверить в Render → Environment:\n"
            "• OPENAI_API_KEY (обязательно)\n"
            "• AI_ENABLED=1\n"
            "• OPENAI_MODEL=gpt-4.1-mini (или другой доступный)\n"
            "• (опционально) OPENAI_BASE_URL (если используешь прокси)\n\n"
            "Если это free Render — иногда сеть/SSL лагает. Ретраи уже включены."
        )
