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
        game = (profile.get("game") or "Warzone").strip()
        platform = (profile.get("platform") or "PC").strip()
        input_ = (profile.get("input") or "Controller").strip()
        diff = (profile.get("difficulty") or "Normal").strip()
        bf6_class = (profile.get("bf6_class") or "Assault").strip()

        # Language rule
        if game.upper() == "BF6":
            lang = "Use EN for BF6 settings terms. You may explain briefly in RU."
        else:
            lang = "Answer in Russian (RU)."

        # Style
        if diff.lower().startswith("demon"):
            style = "DEMON teammate coach: ultra-specific, aggressive efficiency, NOT toxic."
        elif diff.lower().startswith("pro"):
            style = "PRO teammate coach: structured micro+macro."
        else:
            style = "NORMAL teammate coach: clear and actionable."

        system = (
            "You are an elite FPS coach & teammate.\n"
            f"{lang}\n{style}\n"
            "Always output:\n"
            "NOW: (next fight actions)\n"
            "NEXT: (20-30 min training)\n"
            "SETTINGS: (only if relevant)\n"
            "ONE question max if needed.\n"
            "No generic templates.\n"
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "system", "content": f"PROFILE game={game} platform={platform} input={input_} bf6_class={bf6_class} difficulty={diff}"},
        ]

        for t in (history or [])[-12:]:
            role = t.get("role") if t.get("role") in ("user", "assistant", "system") else "user"
            messages.append({"role": role, "content": str(t.get("content", ""))})

        messages.append({"role": "user", "content": user_text})

        client = self._client()

        # Responses API (new)
        try:
            r = client.responses.create(model=self.model, input=messages)
            out = getattr(r, "output_text", None)
            if out:
                return out.strip()
        except Exception:
            pass

        # Fallback: chat.completions
        try:
            cc = client.chat.completions.create(model=self.model, messages=messages)
            text = cc.choices[0].message.content or ""
            return text.strip() or "AI empty."
        except Exception as e:
            return f"🧠 AI ERROR: {e}\nПроверь OPENAI_API_KEY в Render ENV."
