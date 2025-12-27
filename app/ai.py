# -*- coding: utf-8 -*-
import requests
from typing import List, Dict, Optional

class AIEngine:
    def __init__(self, *, api_key: str, model: str, log):
        self.api_key = api_key
        self.model = model
        self.log = log

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _fallback(self, user_text: str) -> str:
        # Базовый ответ если ключа нет/ошибка
        return (
            "🧠 Brain v3 (BOOT MODE)\n"
            "Опиши ситуацию (где умер/ошибка/что хочешь улучшить) — дам план действий.\n\n"
            f"Ты написал: {user_text[:500]}"
        )

    def reply(self, system: str, messages: List[Dict[str, str]]) -> str:
        if not self.enabled:
            return self._fallback(messages[-1]["content"] if messages else "")

        try:
            url = "https://api.openai.com/v1/responses"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            # превращаем chat messages в input
            # responses API принимает input как массив content blocks; делаем просто текстом
            convo_text = system.strip() + "\n\n"
            for m in messages[-30:]:
                role = m.get("role", "user")
                convo_text += f"{role.upper()}: {m.get('content','')}\n"

            payload = {
                "model": self.model,
                "input": convo_text,
                "max_output_tokens": 500,
            }

            r = requests.post(url, headers=headers, json=payload, timeout=60)
            data = r.json()

            # вытащим текст
            out = ""
            for item in (data.get("output") or []):
                for c in (item.get("content") or []):
                    if c.get("type") == "output_text":
                        out += c.get("text", "")
            out = (out or "").strip()

            if not out:
                self.log.warning("OpenAI empty output: %s", str(data)[:500])
                return self._fallback(messages[-1]["content"] if messages else "")

            return out

        except Exception as e:
            self.log.warning("OpenAI error: %r", e)
            return self._fallback(messages[-1]["content"] if messages else "")