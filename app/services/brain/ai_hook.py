# app/services/brain/ai_hook.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Mapping

import certifi
import httpx
from openai import OpenAI

from app.services.brain.intents import IntentResult, classify_intent
from app.services.brain.knowledge_context import KnowledgeContext
from app.services.brain.prompt_builder import PromptBuilder
from app.services.brain.response_policy import ResponsePolicy, get_response_policy


def _s(value: Any, default: str = "") -> str:
    try:
        text = "" if value is None else str(value).strip()
    except Exception:
        text = ""
    return text or default


_TILT_WORDS = (
    "тильт", "горю", "сгорел", "бесит", "достало", "ненавижу", "психую", "злюсь",
    "паника", "страшно", "руки трясутся", "слил", "сливаю", "рандомы", "клоуны",
)
_LOW_CONF_WORDS = ("я ноль", "я слабый", "не умею", "не получается", "я не могу", "я дно")
_HYPE_WORDS = ("погнали", "хочу разнести", "хочу топ", "топ1", "тащу", "доминировать")
_CALM_WORDS = ("спокойно", "давай по факту", "без воды", "по делу", "анализ")


def detect_emotion(user_text: str) -> tuple[str, str]:
    text = " ".join((user_text or "").lower().replace("\n", " ").split())
    exclamations = (user_text or "").count("!") + (user_text or "").count("‼")
    letters = [c for c in (user_text or "") if c.isalpha()]
    caps = sum(1 for c in letters if c.isupper())
    ratio = caps / max(1, len(letters))

    intensity = "high" if exclamations >= 3 or ratio > 0.28 else "mid" if exclamations == 2 or ratio > 0.18 else "low"

    if any(x in text for x in _TILT_WORDS):
        if any(x in text for x in ("паник", "страш", "руки тряс")):
            return "anxiety", intensity
        return "tilt", intensity
    if any(x in text for x in _LOW_CONF_WORDS):
        return "low_conf", intensity
    if any(x in text for x in _HYPE_WORDS):
        return "hype", intensity
    if any(x in text for x in _CALM_WORDS):
        return "calm", intensity
    return "neutral", intensity


def _temperature(profile: Mapping[str, Any], user_text: str) -> float:
    brain = _s(profile.get("difficulty") or profile.get("brain_mode"), "Normal").upper()
    state, intensity = detect_emotion(user_text)
    value = 0.62
    if brain == "PRO":
        value = 0.68
    elif brain == "DEMON":
        value = 0.72
    if state in {"tilt", "anxiety"}:
        value -= 0.08 if intensity == "high" else 0.05
    elif state == "hype":
        value += 0.03
    return max(0.42, min(0.82, value))


def _clean_similarity(text: str) -> str:
    return " ".join(_s(text).lower().replace("\n", " ").split())


@dataclass
class AIHook:
    api_key: str
    model: str = "gpt-4.1-mini"
    max_attempts: int = 4
    base_sleep: float = 0.7
    prompt_builder: PromptBuilder | None = None

    def _client(self) -> OpenAI:
        timeout = httpx.Timeout(connect=20.0, read=75.0, write=45.0, pool=75.0)
        limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
        http_client = httpx.Client(
            timeout=timeout,
            limits=limits,
            verify=certifi.where(),
            headers={"User-Agent": "BLACK-CROWN-OPS/2.0"},
        )
        base_url = _s(os.getenv("OPENAI_BASE_URL"), "") or None
        return OpenAI(api_key=self.api_key, base_url=base_url, http_client=http_client)

    def _looks_like_repeat(self, history: list[dict], candidate: str) -> bool:
        last = ""
        for item in reversed(history or []):
            if _s(item.get("role")).lower() == "assistant":
                last = _s(item.get("content"))
                break
        if not last or not candidate:
            return False
        a = _clean_similarity(candidate)
        b = _clean_similarity(last)
        return bool(a[:220] and a[:220] == b[:220])

    def _anti_repeat_hint(self) -> dict:
        return {
            "role": "system",
            "content": (
                "Quality retry: the candidate was too similar to the previous assistant answer. "
                "Keep the facts unchanged, but use a different opening, structure and tactical angle. "
                "Do not add invented details."
            ),
        }

    def generate(
        self,
        *,
        profile: dict[str, Any],
        history: list[dict],
        user_text: str,
        intent_result: IntentResult | None = None,
        policy: ResponsePolicy | None = None,
        knowledge: KnowledgeContext | None = None,
        player_context: Mapping[str, Any] | None = None,
    ) -> str:
        intent_result = intent_result or classify_intent(user_text, profile)
        policy = policy or get_response_policy(intent_result, profile)
        knowledge = knowledge or KnowledgeContext.unknown()
        emotion_state, emotion_intensity = detect_emotion(user_text)
        builder = self.prompt_builder or PromptBuilder()

        messages = builder.build_messages(
            profile=profile,
            history=history or [],
            user_text=user_text,
            intent=intent_result,
            policy=policy,
            knowledge=knowledge,
            emotion_state=emotion_state,
            emotion_intensity=emotion_intensity,
            player_context=player_context,
        )

        client = self._client()
        temp = _temperature(profile, user_text)
        last_error: Exception | None = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temp,
                )
                output = (response.choices[0].message.content or "").strip()

                if output and self._looks_like_repeat(history or [], output):
                    retry_messages = [*messages, self._anti_repeat_hint()]
                    retry = client.chat.completions.create(
                        model=self.model,
                        messages=retry_messages,
                        temperature=min(0.86, temp + 0.05),
                    )
                    output = (retry.choices[0].message.content or "").strip()

                if output:
                    return output

                return (
                    "🧠 Пустой ответ от модели.\n"
                    "Напиши ситуацию ещё раз одной строкой — без потери текущего профиля."
                )
            except Exception as exc:
                last_error = exc
                if attempt < self.max_attempts:
                    time.sleep(self.base_sleep * attempt)

        return (
            "🧠 ИИ временно недоступен после повторных попыток.\n"
            f"Ошибка: {type(last_error).__name__ if last_error else 'unknown'}.\n"
            "Проверь OPENAI_API_KEY / OPENAI_MODEL и повтори запрос."
        )
