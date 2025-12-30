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
    if "demon" in d or "демон" in d:
        return "DEMON"
    if "pro" in d or "проф" in d:
        return "PRO"
    return "NORMAL"


def _voice_mode(profile: Dict[str, Any]) -> str:
    """
    IMPORTANT:
    Профиль хранит voice как "TEAMMATE"/"COACH".
    Поддерживаем ОБА ключа: voice и voice_mode (для совместимости).
    TEAMMATE — дефолт.
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
      {"role":"user"/"assistant", "content":"..."}  OR store variants
    Keep only valid roles.
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


def _is_greeting(text: str) -> bool:
    t = _s(text).lower()
    if not t:
        return True
    greetings = ("привет", "здар", "хай", "hi", "hello", "йо", "ку", "добрый", "здравствуйте")
    return (len(t) <= 14 and any(g in t for g in greetings)) or t in ("start", "/start")


def _is_too_short(text: str) -> bool:
    t = _s(text)
    return len(t) < 12


def _should_suggest_coach(user_text: str) -> bool:
    """
    Умный триггер: когда запрос похож на "систему/разбор/план/метрики/ранги/стабильность".
    Мы НЕ переключаем голос сами — только предлагаем.
    """
    t = _s(user_text).lower()
    if not t:
        return False

    # Сильные маркеры "коуч-режима"
    strong = (
        "план", "программа", "расписание", "режим", "система", "курс",
        "трениров", "дрилл", "рутина", "прогресс", "метрик", "kpi",
        "разбор", "vod", "ошибк", "анализ", "стратег", "ротац", "позицион",
        "плейбук", "макро", "микро", "ранг", "рейтинг", "сорев", "турнир",
        "хочу стабильно", "стабильн", "перестать умирать", "как улучшить",
        "сделай мне", "составь", "раскатай", "по шагам", "по пунктам",
        "топ", "элит", "как ты", "максимум", "на максимум",
    )

    # Если текст длинный — чаще коуч полезен
    if len(t) >= 80:
        return True

    return any(k in t for k in strong)


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
        timeout = httpx.Timeout(connect=20.0, read=75.0, write=45.0, pool=75.0)
        limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)

        http_client = httpx.Client(
            timeout=timeout,
            limits=limits,
            verify=certifi.where(),
            headers={"User-Agent": "GGBF6-WARZON-BOT/1.0 (Render)"},
        )

        base_url = _s(os.getenv("OPENAI_BASE_URL"), "") or None
        return OpenAI(api_key=self.api_key, base_url=base_url, http_client=http_client)

    # ----------------------------
    # Elite prompting (TEAMMATE default, COACH elite)
    # ----------------------------
    def _system_prompt(self, profile: Dict[str, Any], user_text: str = "") -> str:
        game = _s(profile.get("game"), "Warzone")
        platform = _s(profile.get("platform"), "PC")
        input_ = _s(profile.get("input"), "Controller")
        diff = _s(profile.get("difficulty"), "Normal")
        bf6_class = _s(profile.get("bf6_class"), "Assault")
        role = _s(profile.get("role"), "Flex")
        zombies_map = _s(profile.get("zombies_map"), "Ashes")
        voice = _voice_mode(profile)
        style = _difficulty_style(diff)

        t = _s(user_text, "")
        is_greet = _is_greeting(t)
        is_short = _is_too_short(t)
        suggest_coach = _should_suggest_coach(t) and voice == "TEAMMATE"

        global_rules = (
            "ОБЯЗАТЕЛЬНО:\n"
            "- Пиши по-русски (настройки BF6 могут быть EN в меню — но ответы пользователю тут RU).\n"
            "- Не повторяйся. Запрещено начинать ответы одинаковыми фразами.\n"
            "- Никакой воды. Каждая строка должна помогать победить.\n"
            "- 0–1 уточняющий вопрос максимум. Если вводных мало — дай базовый план + один вопрос.\n"
            "- Не токсичь. Можно дерзко/с юмором, но без оскорблений.\n"
            "- Не пиши как лог/доклад о профиле. Используй профиль как скрытое знание.\n"
        )

        style_directive = (
            "РЕЖИМ NORMAL: спокойная уверенность, четко.\n"
            "РЕЖИМ PRO: жёстче приоритизация, меньше лишнего.\n"
            "РЕЖИМ DEMON: максимально дерзко и по делу, режешь лишнее, давишь на результат.\n"
            f"Текущий стиль: {style}\n"
        )

        context = (
            "КОНТЕКСТ (не перечисляй как лог, используй как знание):\n"
            f"- game={game}, platform={platform}, input={input_}, difficulty={diff}, role={role}, bf6_class={bf6_class}, zombies_map={zombies_map}\n"
        )

        greeting_block = (
            "ЕСЛИ пользователь пишет просто привет/1-2 слова:\n"
            "- Ответь коротко, как человек.\n"
            "- Дай мини-меню 3 пунктами (что можешь сделать прямо сейчас).\n"
            "- Попроси ОДНУ вводную строкой: «игра | input | где умираешь | цель».\n"
        )

        teammate_block = (
            "ТЫ — TEAMMATE (по умолчанию). Ты максимально открытый, живой и уверенный, но ультра-умный.\n"
            "СХЕМА (гибридная, без занудства):\n"
            "A) 1 строка — что ты понял / главный косяк\n"
            "B) 3–6 буллетов — что делать СЕЙЧАС в бою\n"
            "C) 2–4 буллета — мини-тренировка на 10–15 минут (если уместно)\n"
            "D) 1 метрика (как понять, что стало лучше)\n"
            "Правила TEAMMATE:\n"
            "- Общайся как лучший напарник, не как преподаватель.\n"
            "- Можно лёгкий треш-ток в сторону ситуации («это был суицидный пик»), но без токсика.\n"
            "- Если пользователь просит «универсально» — давай универсальные правила + уточни 1 вопрос.\n"
        )

        coach_block = (
            "ТЫ — COACH. Максимально элитный, структурный, как тренер топ-уровня.\n"
            "СХЕМА (строго, но живо):\n"
            "1) Диагноз (1–2 строки, без воды)\n"
            "2) Сейчас (боевой протокол): 5–9 коротких пунктов (приоритет сверху вниз)\n"
            "3) Тренировка (15–25 минут): 3 блока с таймингом + цель каждого\n"
            "4) Метрика прогресса: 1–3 измеримых показателя\n"
            "5) Ошибка-ловушка: 1 пункт «что НЕ делать»\n"
            "Правила COACH:\n"
            "- Никаких одинаковых болванок.\n"
            "- Если вводных мало — 1 вопрос максимум, но всё равно выдавай план.\n"
            "- Пиши так, чтобы можно было выполнить буквально по шагам.\n"
        )

        game_bias = (
            "ОСОБЕННОСТИ (используй по ситуации):\n"
            "- Warzone/BO7: роль влияет на стиль файта (Entry/IGL/Support/Flex/Slayer).\n"
            "- BF6: класс влияет на позиционку/темп (Assault/Recon/Engineer/Medic).\n"
            "- Если юзер про Zombies: больше про маршрут/экономику/перки/контроль волны.\n"
        )

        rescue_block = ""
        if is_greet or is_short:
            rescue_block = (
                "РЕЖИМ СПАСЕНИЯ (вводных мало):\n"
                "- Дай универсальный микро-план под текущую игру из профиля.\n"
                "- В конце задай ОДИН вопрос: где именно умираешь чаще всего?\n"
            )

        coach_offer_block = ""
        if suggest_coach:
            coach_offer_block = (
                "ДОП. ПРАВИЛО (апсейл без автопереключения):\n"
                "- Если запрос выглядит как «серьёзный разбор/система/план/метрики», "
                "в конце ответа добавь ОДНУ короткую строку-предложение:\n"
                "  «Хочешь элитно по пунктам (Коуч)? → 💎 Premium → 🎙 Голос → 📚 Коуч»\n"
                "- НИКОГДА не говори, что ты уже переключил режим. НИКАКИХ автосмен.\n"
            )

        voice_block = coach_block if voice == "COACH" else teammate_block

        return (
            "Ты — ultra-premium FPS Coach Bot (Warzone / BO7 / BF6 + Zombies).\n"
            f"Voice mode: {voice}\n\n"
            + global_rules
            + "\n"
            + style_directive
            + "\n"
            + greeting_block
            + ("\n" + rescue_block if rescue_block else "")
            + ("\n" + coach_offer_block if coach_offer_block else "")
            + "\n"
            + voice_block
            + "\n"
            + game_bias
            + "\n"
            + context
            + "\n"
            "ЗАПРЕЩЕНО:\n"
            "- Пустые общие слова («старайся лучше», «просто тренируйся»).\n"
            "- Повторять один и тот же старт фразы.\n"
        ).strip()

    def _temperature(self, profile: Dict[str, Any]) -> float:
        style = _difficulty_style(_s(profile.get("difficulty"), "Normal"))
        voice = _voice_mode(profile)
        # TeamMate — чуть живее; Coach — чуть суше/точнее.
        if voice == "COACH":
            if style == "DEMON":
                return 0.62
            if style == "PRO":
                return 0.58
            return 0.54
        # TEAMMATE
        if style == "DEMON":
            return 0.78
        if style == "PRO":
            return 0.72
        return 0.66

    def _build_messages(self, profile: Dict[str, Any], history: List[dict], user_text: str) -> List[dict]:
        system = self._system_prompt(profile, user_text=user_text)

        msgs: List[dict] = [{"role": "system", "content": system}]
        msgs.extend(_extract_recent(history or [], max_turns=20))
        msgs.append({"role": "user", "content": _limit_text(user_text, 3000)})

        return msgs

    def _looks_like_repeat(self, history: List[dict], candidate: str) -> bool:
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

        if not a or not b:
            return False

        if a[:220] and a[:220] == b[:220]:
            return True

        if len(a) < 420 and len(b) < 420 and a[:160] == b[:160]:
            return True

        return False

    def _anti_repeat_hint(self, profile: Dict[str, Any]) -> str:
        voice = _voice_mode(profile)
        if voice == "COACH":
            return (
                "ВАЖНО: прошлый ответ слишком похож на предыдущий.\n"
                "Сделай другой заход:\n"
                "- начни с другой формулировки диагноза\n"
                "- поменяй порядок пунктов\n"
                "- добавь 1 метрику и 1 ловушку\n"
                "Не используй те же первые слова."
            )
        return (
            "ВАЖНО: не повторяйся.\n"
            "Ответь по-новому как тиммейт:\n"
            "- другие первые слова\n"
            "- другой угол (позиционка/тайминг/дисциплина)\n"
            "- 1 вопрос максимум.\n"
        )

    def generate(self, *, profile: Dict[str, Any], history: List[dict], user_text: str) -> str:
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

                if self._looks_like_repeat(history or [], text_out):
                    msgs.append({"role": "system", "content": self._anti_repeat_hint(profile)})
                    resp2 = client.chat.completions.create(
                        model=self.model,
                        messages=msgs,
                        temperature=min(0.85, temp + 0.06),
                    )
                    text_out = (resp2.choices[0].message.content or "").strip()

                if not text_out:
                    return (
                        "🧠 ИИ вернул пустоту (да, бывает 😅).\n"
                        "Дай одной строкой:\n"
                        "Игра | input | где умираешь | цель\n"
                        "и я соберу план."
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
