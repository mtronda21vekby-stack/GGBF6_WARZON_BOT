# app/services/brain/ai_hook.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import certifi
import httpx
from openai import OpenAI


# ----------------------------
# Helpers: styles / safety
# ----------------------------
def _s(val: Any, default: str = "") -> str:
    try:
        v = "" if val is None else str(val)
        v = v.strip()
        return v if v else default
    except Exception:
        return default


def _difficulty_style(diff: str) -> str:
    d = (diff or "Normal").lower()
    if "demon" in d:
        return "DEMON"
    if "pro" in d:
        return "PRO"
    return "NORMAL"


def _voice_mode(profile: Dict[str, Any]) -> str:
    """
    IMPORTANT:
    В твоём проекте профиль хранит voice как "TEAMMATE"/"COACH".
    Раньше тут читалось "voice_mode" -> из-за этого коуч мог не включаться.
    Теперь поддерживаем ОБА ключа (voice и voice_mode), ничего не ломаем.
    """
    v = _s((profile or {}).get("voice") or (profile or {}).get("voice_mode"), "TEAMMATE").upper()
    return "COACH" if "COACH" in v else "TEAMMATE"


def _limit_text(text: str, max_chars: int = 4000) -> str:
    t = _s(text, "")
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 20] + "\n…(обрезано)"


def _extract_recent(history: List[dict], max_turns: int = 20) -> List[dict]:
    """
    history item format expected:
      {"role":"user"/"assistant", "content":"..."}  OR your store variants
    We keep only valid roles.
    """
    out: List[dict] = []
    for m in (history or [])[-max_turns:]:
        role = _s(m.get("role"), "").lower()
        content = m.get("content")
        if role in ("user", "assistant") and content:
            out.append({"role": role, "content": _limit_text(str(content), 2000)})
    return out


def _clean_for_similarity(s: str) -> str:
    return " ".join(_s(s).lower().replace("\n", " ").split())


# ----------------------------
# Main AI Hook
# ----------------------------
@dataclass
class AIHook:
    api_key: str
    model: str = "gpt-4.1-mini"

    # retry config (Render free иногда шатает сеть)
    max_attempts: int = 4
    base_sleep: float = 0.7

    def _client(self) -> OpenAI:
        # Render иногда даёт сетевые глюки -> таймауты + нормальный SSL
        timeout = httpx.Timeout(connect=20.0, read=75.0, write=45.0, pool=75.0)
        limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)

        http_client = httpx.Client(
            timeout=timeout,
            limits=limits,
            verify=certifi.where(),
            headers={
                "User-Agent": "GGBF6-WARZON-BOT/1.0 (Render)",
            },
        )

        base_url = _s(os.getenv("OPENAI_BASE_URL"), "") or None
        return OpenAI(api_key=self.api_key, base_url=base_url, http_client=http_client)

    def _system_prompt(self, profile: Dict[str, Any]) -> str:
        game = _s(profile.get("game"), "Warzone")
        platform = _s(profile.get("platform"), "PC")
        input_ = _s(profile.get("input"), "Controller")
        diff = _s(profile.get("difficulty"), "Normal")
        bf6_class = _s(profile.get("bf6_class"), "Assault")
        role = _s(profile.get("role"), "Flex")
        voice = _voice_mode(profile)
        style = _difficulty_style(diff)

        # RU everywhere, but BF6 device settings can be EN — это НЕ тут, это в worlds/ тексте настроек.
        if voice == "COACH":
            tone_block = (
                "Ты — элитный FPS коуч, но живой.\n"
                "Структура ответа:\n"
                "1) Диагноз (1-2 строки)\n"
                "2) СЕЙЧАС (в бою: 3-6 коротких пунктов)\n"
                "3) ДАЛЬШЕ (тренировка/настройки: 3-6 пунктов)\n"
                "Правила:\n"
                "- Никаких шаблонов и одинаковых фраз.\n"
                "- Если вводных мало — максимум 1-2 уточняющих вопроса, иначе сразу план.\n"
                "- Пиши по-русски. Лёгкий юмор разрешён, кринж — запрещён.\n"
            )
        else:
            tone_block = (
                "Ты — сильный тиммейт (не коуч-лекция), но умный.\n"
                "Стиль:\n"
                "- Разговорно, уверенно, коротко.\n"
                "- Можешь подколоть, но без токсика.\n"
                "- Сначала 1-2 ключевые мысли, потом быстрый план.\n"
                "Правила:\n"
                "- Не повторяй одну и ту же фразу.\n"
                "- Если мало вводных — 1 вопрос максимум, иначе действуй.\n"
                "- Пиши по-русски. Юмор — да, занудство — нет.\n"
            )

        return (
            "Ты — ultra-premium FPS Coach Bot (Warzone / BO7 / BF6).\n"
            f"Brain style: {style}\n"
            f"Voice mode: {voice}\n\n"
            f"{tone_block}\n"
            "Контекст игрока (внутри ответа не перечисляй как лог, используй как знание):\n"
            f"- game={game}, platform={platform}, input={input_}, difficulty={diff}, role={role}, bf6_class={bf6_class}\n"
            "Если юзер пишет просто 'привет' — отвечай нормально, как человек, и мягко попроси вводные.\n"
            "Запрещено: повторять одну и ту же болванку, отвечать пустыми общими словами.\n"
        ).strip()

    def _temperature(self, profile: Dict[str, Any]) -> float:
        style = _difficulty_style(_s(profile.get("difficulty"), "Normal"))
        # чуть живее, но без шизы
        if style == "DEMON":
            return 0.78
        if style == "PRO":
            return 0.72
        return 0.66

    def _build_messages(self, profile: Dict[str, Any], history: List[dict], user_text: str) -> List[dict]:
        system = self._system_prompt(profile)

        msgs: List[dict] = [{"role": "system", "content": system}]
        msgs.extend(_extract_recent(history or [], max_turns=20))
        msgs.append({"role": "user", "content": _limit_text(user_text, 3000)})

        return msgs

    def _looks_like_repeat(self, history: List[dict], candidate: str) -> bool:
        """
        Детектор залипания: если ответ слишком похож на предыдущий assistant.
        """
        cand = _s(candidate, "")
        if not cand:
            return False

        last = ""
        for m in reversed(history or []):
            if _s(m.get("role"), "").lower() == "assistant":
                last = _s(m.get("content"), "")
                break
        if not last:
            return False

        a = _clean_for_similarity(cand)
        b = _clean_for_similarity(last)

        # если почти одинаковые первые 220 символов — это залипание
        return a[:220] and (a[:220] == b[:220])

    def _anti_repeat_hint(self, profile: Dict[str, Any]) -> str:
        voice = _voice_mode(profile)
        if voice == "COACH":
            return (
                "ВАЖНО: твой прошлый ответ был слишком похож на предыдущий. "
                "Сделай другой угол: уточни 1 вопрос ИЛИ дай план через другие пункты. "
                "Не начинай с тех же слов."
            )
        return (
            "ВАЖНО: не повторяйся. Ответь по-новому, как тиммейт: "
            "другие первые слова, другой угол, 1 вопрос максимум."
        )

    def generate(self, *, profile: Dict[str, Any], history: List[dict], user_text: str) -> str:
        """
        Главная точка: вызывает OpenAI, ретраи, анти-повтор, человекоподобный стиль.
        """
        client = self._client()
        msgs = self._build_messages(profile, history or [], user_text)

        last_err: Optional[Exception] = None
        temp = self._temperature(profile)

        for attempt in range(1, self.max_attempts + 1):
            try:
                resp = client.chat.completions.create(
                    model=self.model,
                    messages=msgs,
                    temperature=temp,
                )
                text_out = (resp.choices[0].message.content or "").strip()

                # анти-залипание: если повторился — добавляем хинт и делаем 1 повторный запрос
                if self._looks_like_repeat(history or [], text_out):
                    msgs.append({"role": "system", "content": self._anti_repeat_hint(profile)})
                    resp2 = client.chat.completions.create(
                        model=self.model,
                        messages=msgs,
                        temperature=min(0.85, temp + 0.05),
                    )
                    text_out = (resp2.choices[0].message.content or "").strip()

                if not text_out:
                    return (
                        "🧠 ИИ вернул пустоту (да, бывает 😅).\n"
                        "Напиши ещё раз одной строкой:\n"
                        "Игра | input | где умираешь | что хочешь улучшить."
                    )

                return text_out

            except Exception as e:
                last_err = e
                time.sleep(self.base_sleep * attempt)

        return (
            "🧠 ИИ: ERROR (после ретраев)\n"
            f"{type(last_err).__name__}: {last_err}\n\n"
            "Что проверить в Render → Environment:\n"
            "1) OPENAI_API_KEY = твой ключ\n"
            "2) AI_ENABLED=1\n"
            "3) OPENAI_MODEL (по умолчанию gpt-4.1-mini)\n"
            "4) Если используешь прокси: OPENAI_BASE_URL\n\n"
            "Если Render free — сеть иногда шатает. Ретраи уже включены."
        )
