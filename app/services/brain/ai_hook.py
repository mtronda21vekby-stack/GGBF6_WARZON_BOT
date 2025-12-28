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
        bf6_class = (profile.get("bf6_class") or "").strip()

        is_bf6 = game.upper() == "BF6"
        lang_rule = (
            "BF6: settings terms in English. You may explain briefly in Russian."
            if is_bf6
            else "Warzone/BO7: отвечай на русском (RU first)."
        )

        if diff.lower().startswith("demon"):
            style = "DEMON teammate-coach: aggressive, ultra-specific, no fluff, not toxic."
        elif diff.lower().startswith("pro"):
            style = "PRO teammate-coach: structured, precise, micro+macro."
        else:
            style = "NORMAL teammate-coach: clear, actionable."

        system = (
            "You are an elite FPS coach & teammate.\n"
            f"{lang_rule}\n{style}\n"
            "Answer format ALWAYS:\n"
            "1) NOW (next fight actions)\n"
            "2) NEXT (20–30 min training)\n"
            "3) SETTINGS (only if relevant; respect game/platform/input)\n"
            "4) One clarifying question (max 1) only if needed.\n"
            "No generic templates. Must be tailored to user input.\n"
        )

        profile_line = f"PROFILE: game={game}; platform={platform}; input={input_}; difficulty={diff}; bf6_class={bf6_class}"
        last = history[-14:] if history else []

        messages = [{"role": "system", "content": system}, {"role": "system", "content": profile_line}]
        for t in last:
            role = t.get("role")
            if role not in ("user", "assistant", "system"):
                role = "user"
            messages.append({"role": role, "content": str(t.get("content", ""))})
        messages.append({"role": "user", "content": user_text})

        client = self._client()

        # 1) Try Responses API
        try:
            resp = client.responses.create(model=self.model, input=messages)
            out = getattr(resp, "output_text", None)
            if out:
                return out.strip()
        except Exception:
            pass

        # 2) Fallback: Chat Completions
        try:
            cc = client.chat.completions.create(model=self.model, messages=messages)
            text = cc.choices[0].message.content or ""
            return text.strip() or "AI returned empty."
        except Exception as e:
            return f"🧠 AI ERROR: {e}\n(Проверь OPENAI_API_KEY в Render ENV.)"
