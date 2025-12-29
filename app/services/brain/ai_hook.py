# app/services/brain/ai_hook.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List
import os
import asyncio

import httpx
import certifi

try:
    from openai import AsyncOpenAI  # SDK 1.x
except Exception:
    AsyncOpenAI = None
    from openai import OpenAI  # fallback


# ---------- helpers ----------

def _difficulty_style(diff: str) -> str:
    d = (diff or "Normal").lower()
    if "demon" in d or "демон" in d:
        return "DEMON"
    if "pro" in d or "проф" in d:
        return "PRO"
    return "NORMAL"


def _norm_game(game: str) -> str:
    g = (game or "Warzone").lower()
    if "bf6" in g or "battlefield" in g:
        return "BF6"
    if "bo7" in g or "black" in g:
        return "BO7"
    return "Warzone"


def _last(history: List[dict], n: int = 20) -> List[dict]:
    return history[-n:] if history else []


def _looks_like_coach_request(text: str) -> bool:
    """
    Если юзер явно просит разбор/план/настройки — включаем COACH структуру.
    Иначе — TEAMMATE диалог.
    """
    t = (text or "").strip().lower()
    if not t:
        return False

    keywords = [
        "разбор", "план", "тренировка", "настрой", "настройки", "сенса", "sens",
        "помоги", "как улучшить", "что делать", "почему умираю", "диагноз",
        "ошибка", "позицион", "мувмент", "aim", "аим", "vod", "клип", "таймкод",
    ]
    return any(k in t for k in keywords)


def _voice(profile: Dict[str, Any], user_text: str) -> str:
    """
    Выбор голоса:
    - если в профиле есть voice = "COACH"/"TEAMMATE" — уважаем
    - иначе авто по тексту
    """
    v = str((profile or {}).get("voice") or "").strip().upper()
    if v in ("COACH", "TEAMMATE"):
        return v
    return "COACH" if _looks_like_coach_request(user_text) else "TEAMMATE"


# ---------- system prompt ----------

def _system_prompt(profile: Dict[str, Any], user_text: str) -> str:
    game = _norm_game(profile.get("game", "Warzone"))
    platform = profile.get("platform", "PC")
    input_ = profile.get("input", "Controller")
    diff = profile.get("difficulty", "Normal")
    bf6_class = profile.get("bf6_class", "Assault")

    style = _difficulty_style(diff)
    voice = _voice(profile, user_text)

    # Режимы тона
    if style == "DEMON":
        tone = (
            "Тон: демонический элитный тиммейт.\n"
            "Юмор: тёмная ирония/сарказм, уверенно, но без оскорблений.\n"
        )
    elif style == "PRO":
        tone = (
            "Тон: профессиональный коуч/тиммейт.\n"
            "Юмор: сухая ирония иногда, очень по делу.\n"
        )
    else:
        tone = (
            "Тон: сильный тиммейт.\n"
            "Юмор: лёгкий, поддерживающий.\n"
        )

    # Общие правила (анти-шаблон)
    base_rules = """
ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА:
- Всегда отвечай на русском.
- Не используй шаблоны и одинаковые фразы.
- Не повторяй приветствия.
- Не говори, что ты ИИ.
- Если данных мало — максимум 1–2 уточнения, иначе сразу давай решение.
- Ты тиммейт, который хочет выиграть, а не учитель из учебника.
""".strip()

    # Голоса: COACH vs TEAMMATE
    if voice == "COACH":
        voice_rules = """
ФОРМАТ (COACH):
1) Диагноз (1–3 строки, можно с юмором)
2) СЕЙЧАС — что делать прямо в матче (3–7 пунктов)
3) ДАЛЬШЕ — тренировка / привычка / настройка (3–7 пунктов)
""".strip()
    else:
        voice_rules = """
ФОРМАТ (TEAMMATE):
- Пиши как живой тиммейт в чат: короткие реплики, естественный язык.
- Можно 1–2 микро-списка, но НЕ обязателен формат "Диагноз/Сейчас/Дальше".
- Всё равно давай конкретику (что делать прямо сейчас), но разговорно.
- Иногда вставляй короткие "коллы" (типа: «не репикай», «сдвигайся», «держи выход»).
""".strip()

    # Контекст мира
    world = f"""
Контекст игрока:
- Игра: {game}
- Платформа: {platform}
- Input: {input_}
- Режим: {diff}
- Голос: {voice}
""".strip()

    if game == "BF6":
        world += (
            f"\n- BF6 класс: {bf6_class}\n"
            "Важно: настройки устройств BF6 (PC/Xbox/PS) находятся в кнопках и будут на английском — это нормально.\n"
        )

    return "\n\n".join(
        [
            "Ты — ultra-premium FPS Coach и элитный тиммейт мирового уровня. Твоя цель — доводить игрока до топ-уровня.",
            tone,
            base_rules,
            voice_rules,
            world,
        ]
    ).strip()


# ---------- AI hook ----------

@dataclass
class AIHook:
    api_key: str
    model: str = "gpt-4.1-mini"

    def _async_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(20, read=90),
            limits=httpx.Limits(max_connections=20),
            verify=certifi.where(),
        )

    async def generate(
        self,
        *,
        profile: Dict[str, Any],
        history: List[dict],
        user_text: str,
    ) -> str:
        system = _system_prompt(profile, user_text)

        messages: List[Dict[str, str]] = [{"role": "system", "content": system}]

        for m in _last(history, 20):
            if m.get("role") in ("user", "assistant") and m.get("content"):
                messages.append({"role": m["role"], "content": str(m["content"])})

        messages.append({"role": "user", "content": user_text})

        # Температура зависит от стиля
        style = _difficulty_style(profile.get("difficulty", "Normal"))
        temperature = 0.62 if style == "NORMAL" else (0.72 if style == "PRO" else 0.78)

        last_err = None

        for attempt in range(3):
            try:
                if AsyncOpenAI:
                    http_client = self._async_client()
                    try:
                        client = AsyncOpenAI(api_key=self.api_key, http_client=http_client)
                        resp = await client.chat.completions.create(
                            model=self.model,
                            messages=messages,
                            temperature=temperature,
                        )
                        return (resp.choices[0].message.content or "").strip()
                    finally:
                        await http_client.aclose()
                else:
                    return await asyncio.to_thread(self._sync_call, messages, temperature)
            except Exception as e:
                last_err = e
                await asyncio.sleep(0.6 * (attempt + 1))

        return (
            "🧠 Я сейчас чуть-чуть приуныл, но это временно 😈\n\n"
            "Диагноз:\n"
            f"{type(last_err).__name__}: {last_err}\n\n"
            "СЕЙЧАС:\n"
            "- Проверь OPENAI_API_KEY в Render\n"
            "- Убедись что AI_ENABLED=1\n"
            "- Сделай Restart сервиса\n\n"
            "ДАЛЬШЕ:\n"
            "- Как только ИИ поднимется — я снова буду полезным, а не декоративным.\n"
        )

    def _sync_call(self, messages: List[Dict[str, str]], temperature: float) -> str:
        client = OpenAI(api_key=self.api_key)
        resp = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
        )
        return (resp.choices[0].message.content or "").strip()
