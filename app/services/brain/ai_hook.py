# app/services/brain/ai_hook.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from openai import OpenAI


@dataclass
class AIHook:
    api_key: str
    model: str = "gpt-4.1-mini"

    def _client(self) -> OpenAI:
        return OpenAI(api_key=self.api_key)

    def generate(self, *, profile: Dict[str, Any], history: List[dict], user_text: str) -> str:
        """
        Возвращает “живой” ответ как тиммейт/коуч.
        BF6: настройки и термины — EN; Warzone/BO7 — RU.
        """
        game = (profile.get("game") or "Warzone").strip()
        platform = (profile.get("platform") or "PC").strip()
        input_ = (profile.get("input") or "Controller").strip()
        diff = (profile.get("difficulty") or "Normal").strip()
        bf6_class = (profile.get("bf6_class") or "").strip()

        # язык
        is_bf6 = game.upper() == "BF6"
        lang_rule = (
            "For BF6: keep SETTINGS TERMS in English (platform/input/settings names), but you may explain briefly in Russian if needed."
            if is_bf6
            else "Для Warzone/BO7 отвечай на русском, термины можно миксовать, но приоритет RU."
        )

        # стиль ответа по режиму
        if diff.lower().startswith("demon"):
            style = "Ты ультра-агрессивный DEMON тиммейт-коуч: коротко, жёстко, конкретно, с приоритетами, без воды. Но без токсика."
        elif diff.lower().startswith("pro"):
            style = "Ты PRO тиммейт-коуч: структурно, точно, даёшь микро- и макро-решения."
        else:
            style = "Ты NORMAL тиммейт-коуч: понятные инструкции и быстрые правки."

        system = (
            "You are an elite FPS coach & teammate. Your goal: maximize win rate and decision quality.\n"
            f"{lang_rule}\n"
            f"{style}\n"
            "Правило ответа: всегда давай блоки:\n"
            "1) СЕЙЧАС (что сделать прямо в следующем бою)\n"
            "2) ДАЛЬШЕ (что тренировать 20-30 минут)\n"
            "3) НАСТРОЙКИ (только если релевантно; учитывай игру/платформу/input)\n"
            "4) 1 вопрос уточнения (максимум один) если реально нужно.\n"
            "Никаких шаблонов-пустышек. Каждый ответ должен быть конкретным под ввод.\n"
        )

        profile_line = f"PROFILE: game={game}; platform={platform}; input={input_}; difficulty={diff}; bf6_class={bf6_class}"

        # берём последние N сообщений, чтобы не раздувать
        last = history[-12:] if history else []
        messages = [{"role": "system", "content": system}]
        messages.append({"role": "system", "content": profile_line})
        for t in last:
            role = t.get("role")
            if role not in ("user", "assistant", "system"):
                role = "user"
            messages.append({"role": role, "content": str(t.get("content", ""))})
        messages.append({"role": "user", "content": user_text})

        # Responses API
        client = self._client()
        resp = client.responses.create(
            model=self.model,
            input=messages,
        )
        # соберём текст
        out = getattr(resp, "output_text", None)
        if out:
            return out.strip()

        # fallback (редко)
        return "Дай вводные: игра | платформа | input | от чего умираешь | дистанция. Я соберу план."
