from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import os
import random
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
    _cached_client: Optional[OpenAI] = field(default=None, init=False, repr=False)

    def _build_http_client(self) -> httpx.Client:
        # Render/free instances can be shaky -> give it breathing room
        timeout = httpx.Timeout(connect=20.0, read=90.0, write=45.0, pool=90.0)
        limits = httpx.Limits(max_keepalive_connections=10, max_connections=30, keepalive_expiry=60.0)

        # trust_env=True is IMPORTANT on some platforms (proxies / CA / env)
        # http2=False tends to be more stable on some free hosts
        return httpx.Client(
            timeout=timeout,
            limits=limits,
            verify=certifi.where(),
            trust_env=True,
            http2=False,
            headers={
                "User-Agent": "ggbf6-warzon-bot/1.0 (Render)",
            },
        )

    def _client(self) -> OpenAI:
        # Cache the client so we reuse connections instead of recreating every request
        if self._cached_client is not None:
            return self._cached_client

        base_url = (os.getenv("OPENAI_BASE_URL", "") or "").strip()
        http_client = self._build_http_client()

        # OpenAI SDK 1.x: pass custom http_client
        if base_url:
            self._cached_client = OpenAI(
                api_key=self.api_key,
                base_url=base_url,
                http_client=http_client,
            )
        else:
            self._cached_client = OpenAI(
                api_key=self.api_key,
                http_client=http_client,
            )

        return self._cached_client

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
- Не отвечай шаблоном. Веди диалог. НЕ повторяй одну и ту же фразу.
- Если вводных мало — задай максимум 1–2 уточнения, иначе сразу давай план.
- Формат ответа:
  1) Диагноз
  2) СЕЙЧАС (что делать прямо в бою)
  3) ДАЛЬШЕ (тренировка/настройки/привычки)

Контекст игрока:
- game={game}
- platform={platform}
- input={input_}
- bf6_class={bf6_class}
- difficulty={diff}

Важно:
- Если пользователь пишет “Привет” или коротко — не залипай. Дай быстрый старт и 1 уточнение.
- Учитывай, что каждый режим = отдельный мир (Warzone / BO7 / BF6).
""".strip()

        msgs: List[Dict[str, str]] = [{"role": "system", "content": system}]

        # keep last N messages
        for m in (history or [])[-20:]:
            role = (m.get("role") or "").strip()
            content = m.get("content")
            if role in ("user", "assistant") and content:
                msgs.append({"role": role, "content": str(content)})

        msgs.append({"role": "user", "content": user_text})

        # More resilient retry with jitter
        last_err: Exception | None = None

        # total tries = 4 (1 + 3 retries)
        for attempt in range(1, 5):
            try:
                resp = client.chat.completions.create(
                    model=self.model,
                    messages=msgs,
                    temperature=0.65 if style == "NORMAL" else 0.75,
                )
                out = (resp.choices[0].message.content or "").strip()
                if out:
                    return out
                return "🧠 ИИ: пустой ответ. Напиши одной строкой: игра | input | что болит — дам план."
            except Exception as e:
                last_err = e

                # If client/connection got poisoned, drop cached client once
                # so next attempt recreates a fresh http connection pool.
                if attempt == 2:
                    self._cached_client = None

                # Backoff with jitter
                base = 0.9 * attempt
                sleep_s = base + random.uniform(0.0, 0.35)
                time.sleep(sleep_s)

        return (
            "🧠 ИИ: ERROR\n"
            f"{type(last_err).__name__}: {last_err}\n\n"
            "Проверь Render → Environment:\n"
            "• OPENAI_API_KEY = твой ключ\n"
            "• AI_ENABLED=1\n"
            "• OPENAI_MODEL=gpt-4.1-mini (или другой доступный)\n"
            "• (опционально) OPENAI_BASE_URL (только если используешь прокси)\n\n"
            "Если это free Render — сеть иногда рвётся. Тут уже:\n"
            "• кэш клиента (reuse соединений)\n"
            "• trust_env=True\n"
            "• увеличенные таймауты\n"
            "• ретраи с jitter\n"
        )
